"""The outbox relay of one home: claim due events, queue their deliveries, mark them.

A tick runs as a periodic task per home (`events.relay_outbox`), so an outage of one home
never stops the other (§13.2). A tick drains: it runs pass after pass while each pass
claimed a full batch, until the home has no due rows, Valkey stops answering or the drain
budget runs out (F1 audit OD-4). A tick cut by the budget is counted: a lasting load above
what a tick drains is the revisit trigger of §12. A pass takes three steps and holds no
transaction while it talks to Valkey (§14 rule 1):

1. claim up to 100 due rows with a 30 s lease (`FOR UPDATE SKIP LOCKED`) and commit, so
   a concurrent pass skips them and a pass that dies releases them when the lease ends;
2. queue one delivery task per subscriber of each event, outside any transaction;
3. in a second transaction mark the passed rows published and hold back the rest.

A row is held back with a pause of `min(2^attempts, 300)` seconds when its deliveries
could not be queued: Valkey out (the pass stops; the rows it did not reach are released
at once), a delivery task missing from this process, or an event type a newer image
wrote. It is never dropped: an event older than 5 minutes pages (§16.4). An event that
reached the queue but was not marked is passed on again; the delivery marks make that
harmless (at-least-once).
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Protocol
from uuid import UUID

import structlog
from sqlalchemy import Interval, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.catalog import DeliveryRoute
from shosai.core.events.delivery import EventDeliveryPayload
from shosai.core.events.publishing import PublishSpans
from shosai.core.events.records import OutboxMessage
from shosai.core.events.resources import EventResources
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.errors import TaskQueueUnavailableError, UnregisteredTaskError
from shosai.core.tasks.payloads import TaskPayload

# ORM не сверяет карту объектов после массового UPDATE: сессия relay объектов не держит.
BULK: Final = {"synchronize_session": False}
PAUSE_EXPONENT_LIMIT: Final = 30
log = structlog.stdlib.get_logger(__name__)


class DeliverySender(Protocol):
    """What the relay needs from the task sender: queue one task within 50 ms."""

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Queue one run of the task; return its task id."""
        ...


@dataclass(frozen=True, slots=True)
class ClaimedEvent:
    """An outbox row the pass holds until its lease ends."""

    id: UUID
    event_type: str
    version: int
    payload: dict[str, Any]
    user_id: UUID | None
    org_id: UUID | None
    traceparent: str | None
    request_id: str | None
    occurred_at: datetime

    def delivery(self, home: Home) -> EventDeliveryPayload:
        """The payload every subscriber's delivery task receives."""
        return EventDeliveryPayload(
            home=home,
            user_id=self.user_id,
            org_id=self.org_id,
            event_id=self.id,
            event_type=self.event_type,
            version=self.version,
            occurred_at=self.occurred_at,
            event=self.payload,
        )


@dataclass(slots=True)
class RelayPass:
    """What a pass, or every pass of a tick, did with the rows it claimed."""

    published: list[UUID] = field(default_factory=list)
    held_back: list[UUID] = field(default_factory=list)
    released: list[UUID] = field(default_factory=list)

    def add(self, other: RelayPass) -> None:
        """Add the rows of a later pass of the same tick."""
        self.published += other.published
        self.held_back += other.held_back
        self.released += other.released

    @property
    def rows(self) -> int:
        """Every row the passes claimed."""
        return len(self.published) + len(self.held_back) + len(self.released)


class OutboxRelay:
    """Passes the events of a home's outbox to the delivery tasks of their subscribers."""

    def __init__(self, resources: EventResources, sender: DeliverySender) -> None:
        self._catalog = resources.catalog
        self._transactions = resources.transactions
        self._metrics = resources.metrics
        self._spans = PublishSpans(resources.tracer_provider)
        self._limits = resources.relay_limits
        self._sender = sender

    async def relay(self, home: Home) -> RelayPass:
        """One tick over the home's due events: passes while each claims a full batch."""
        started = time.monotonic()
        tick, passes = RelayPass(), 0
        while claimed := await self._claim(home):
            passes += 1
            result, queue_down = await self._pass_on(home, claimed)
            await self._settle(home, result)
            tick.add(result)
            if queue_down or len(claimed) < self._limits.batch:
                break
            if time.monotonic() - started >= self._limits.drain_budget.total_seconds():
                self._metrics.count_budget_exhausted(home)
                log.warning(
                    "Relay исчерпал бюджет тика: в outbox остались готовые события",
                    home=home.value,
                    passes=passes,
                )
                break
        self._metrics.observe_tick(home, passes, tick.rows)
        if not passes:
            return tick
        if tick.published:
            self._metrics.count_published(home, len(tick.published))
        log.info(
            "Relay передал события outbox",
            home=home.value,
            passes=passes,
            published=len(tick.published),
            held_back=len(tick.held_back),
            released=len(tick.released),
        )
        return tick

    async def _claim(self, home: Home) -> list[ClaimedEvent]:
        due = (
            select(OutboxMessage.id)
            .where(OutboxMessage.published_at.is_(None), OutboxMessage.available_at <= func.now())
            .order_by(OutboxMessage.available_at, OutboxMessage.id)
            .limit(self._limits.batch)
            .with_for_update(skip_locked=True)
        )
        claim = (
            update(OutboxMessage)
            .where(OutboxMessage.id.in_(due))
            .values(available_at=func.now() + self._limits.lease)
            .returning(
                OutboxMessage.id,
                OutboxMessage.event_type,
                OutboxMessage.version,
                OutboxMessage.payload,
                OutboxMessage.user_id,
                OutboxMessage.org_id,
                OutboxMessage.traceparent,
                OutboxMessage.request_id,
                OutboxMessage.occurred_at,
            )
            .execution_options(**BULK)
        )
        async with self._transactions.begin(TenancyScope(home)) as session:
            rows = (await session.execute(claim)).all()
        # UUIDv7 растёт со временем: события передаются в порядке записи.
        return sorted((ClaimedEvent(*row) for row in rows), key=lambda event: event.id)

    async def _pass_on(self, home: Home, claimed: Sequence[ClaimedEvent]) -> tuple[RelayPass, bool]:
        """Queue the deliveries; True as well when Valkey stopped answering mid-pass."""
        result = RelayPass()
        for index, event in enumerate(claimed):
            routes = self._catalog.routes_of(event.event_type)
            if routes is None:
                self._metrics.count_held_back(home, "unknown_event_type")
                log.error(
                    "Тип события outbox не известен этому образу: событие отложено",
                    home=home.value,
                    event_type=event.event_type,
                    event_id=str(event.id),
                )
                result.held_back.append(event.id)
                continue
            try:
                await self._send(home, event, routes)
            except TaskQueueUnavailableError:
                self._metrics.count_held_back(home, "queue_unavailable")
                result.held_back.append(event.id)
                result.released.extend(rest.id for rest in claimed[index + 1 :])
                return result, True
            except UnregisteredTaskError:
                self._metrics.count_held_back(home, "unregistered_delivery")
                log.exception(
                    "Задача доставки не зарегистрирована в процессе: событие отложено",
                    home=home.value,
                    event_type=event.event_type,
                    event_id=str(event.id),
                )
                result.held_back.append(event.id)
                continue
            result.published.append(event.id)
        return result, False

    async def _send(self, home: Home, event: ClaimedEvent, routes: Sequence[DeliveryRoute]) -> None:
        if not routes:
            return
        payload = event.delivery(home)
        with self._spans.publishing(
            event.id, event.event_type, event.traceparent, event.request_id
        ):
            for route in routes:
                await self._sender.send(route.task, payload)

    async def _settle(self, home: Home, result: RelayPass) -> None:
        async with self._transactions.begin(TenancyScope(home)) as session:
            if result.published:
                await self._mark_published(session, result.published)
            if result.held_back:
                await self._hold_back(session, result.held_back)
            if result.released:
                await self._release(session, result.released)

    async def _mark_published(self, session: AsyncSession, ids: Sequence[UUID]) -> None:
        await session.execute(
            update(OutboxMessage)
            .where(OutboxMessage.id.in_(ids), OutboxMessage.published_at.is_(None))
            .values(published_at=func.now())
            .execution_options(**BULK)
        )

    async def _hold_back(self, session: AsyncSession, ids: Sequence[UUID]) -> None:
        # В SET правые части видят старую строку: пауза — 2^(attempts + 1), то есть 2^новое.
        # Показатель ограничен: power() переполняет double после 2^1023 и уронил бы отметку
        # всей пачки, а дальше предела паузы удвоение ничего не меняет.
        exponent = func.least(OutboxMessage.attempts + 1, PAUSE_EXPONENT_LIMIT)
        pause_seconds = func.least(
            func.power(2, exponent), self._limits.longest_pause.total_seconds()
        )
        await session.execute(
            update(OutboxMessage)
            .where(OutboxMessage.id.in_(ids))
            .values(
                attempts=OutboxMessage.attempts + 1,
                available_at=func.now()
                + func.make_interval(0, 0, 0, 0, 0, 0, pause_seconds, type_=Interval),
            )
            .execution_options(**BULK)
        )

    async def _release(self, session: AsyncSession, ids: Sequence[UUID]) -> None:
        await session.execute(
            update(OutboxMessage)
            .where(OutboxMessage.id.in_(ids))
            .values(available_at=func.now())
            .execution_options(**BULK)
        )
