"""Writing a cost row once per effect key, in the payer's home (inv-9, F6-C1, F6-C6).

The writer runs after the provider call, never around it (§14 rule 1). One transaction in
the payer's home records the effect key in core's ledger; the effect inserts the row and
runs the settlements. A replayed key returns the stored row id and changes nothing. When
the home does not take the write, the row goes to the deferred-record task, which writes it
later with the same key; when the task cannot be queued either, the row is lost, logged and
counted, and the monitor of §16.4 shows it. A call on a latency budget — a Jev decision
(ADR 0069 DL-D2) — hands its row to the same task at once (`later`), so the home's
transaction never sits on its caller's path.

Minute rows of live sessions (F6-C5) are written in batches: one transaction per home, person
and company claims every key of the batch at once, inserts the new rows with one statement and
skips the keys already written, so a replayed flush writes nothing.
"""

from collections.abc import Awaitable, Callable, Sequence
from datetime import timedelta
from typing import Any, Final, Protocol
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.costs.billing import BillingMarks
from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.costs.records import ProviderCost
from shosai.core.ai.costs.settlement import CostSettlements, SettledCost
from shosai.core.ai.metrics import AiMetrics
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.batch import BatchKey, EffectBatch
from shosai.core.idempotency.ledger import EffectKey, EffectLedger, EffectScope
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import RETRY_TRANSIENT, TaskDeclaration, TaskHandler
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.core.tasks.payloads import TaskPayload
from shosai.core.tasks.queues import TaskQueue

# Повторы вызова — до 5 доставок, 3 попытки этапа, сутки ключа клиента — укладываются в 35 дней.
AI_COST: Final = EffectScope("ai.cost", timedelta(days=35))
RECORD_COST: Final = TaskDeclaration(
    name="ai.record_cost",
    queue=TaskQueue.CRITICAL,
    payload=CostEntry,
    deadline=timedelta(seconds=30),
    retry=RETRY_TRANSIENT,
)
log = structlog.stdlib.get_logger(__name__)


class WorkSender(Protocol):
    """What the writer needs from the task sender: queue one task within 50 ms."""

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Queue one run of the task; return its task id."""
        ...


type CostObserver = Callable[[Sequence[CostEntry]], Awaitable[None]]


class RecordedCost(BaseModel):
    """What the ledger keeps for a recorded call: its row id."""

    cost_id: UUID


class CostWriter:
    """Writes cost rows once per effect key; slices never write them themselves."""

    def __init__(
        self,
        transactions: HomeTransactions,
        effects: tuple[EffectLedger, EffectBatch],
        settlements: CostSettlements,
        sender: WorkSender,
        accounting: tuple[AiMetrics, BillingMarks],
    ) -> None:
        self._transactions = transactions
        self._effects, self._batch = effects
        self._settlements = settlements
        self._sender = sender
        # Счётчики процесса и пометки часа в Valkey: по ним сверяются строки (§16.4).
        self._metrics, self._marks = accounting
        self._observers: list[CostObserver] = []

    def observe(self, observer: CostObserver) -> None:
        """Call `observer` with the rows each commit inserted, after it — never on a replay."""
        self._observers.append(observer)

    async def _inserted(self, entries: Sequence[CostEntry]) -> None:
        for entry in entries:
            self._metrics.recorded(entry)
            if entry.cost_rub is None:
                self._metrics.without_rate()
        for observer in self._observers:
            await observer(entries)

    async def record(self, entry: CostEntry) -> None:
        """Write the row now, or hand it to the deferred task when its home does not answer."""
        try:
            await self.write(entry)
        except HomeUnavailableError:
            await self._defer(entry)

    async def later(self, entry: CostEntry) -> None:
        """Hand the row to the deferred-record task at once, off the caller's path (ADR 0069
        DL-D2); without the queue, write it now — a row is never dropped for speed."""
        try:
            await self._sender.send(RECORD_COST, entry)
        except TaskQueueUnavailableError:
            await self.record(entry)
            return
        self._metrics.sent_later()

    async def write(self, entry: CostEntry) -> UUID:
        """Write the row and run the settlements once; return the row id of the effect key."""
        async with self._transactions.begin(entry.scope()) as session:
            result = await self._effects.once(
                session,
                EffectKey(AI_COST, entry.effect_key),
                RecordedCost,
                lambda: self._insert(session, entry),
            )
        if result.replayed:
            await self._repeated([entry])
        else:
            await self._inserted([entry])
        return result.outcome.cost_id

    async def _repeated(self, entries: Sequence[CostEntry]) -> None:
        """Rows whose effect key was already written: billed again, kept once (inv-9)."""
        await self._marks.mark("repeated", ((entry.home, entry.created_at) for entry in entries))

    async def record_many(self, entries: Sequence[CostEntry]) -> None:
        """Write rows in one transaction per home, person and company; defer a home that is down."""
        groups: dict[TenancyScope, dict[str, CostEntry]] = {}
        doubles: list[CostEntry] = []
        for entry in entries:
            # Совпавший ключ в одной пачке — одна строка: первая побеждает, как и в реестре.
            # Область — человека строки: расчёты пишут его строки под его row-level security.
            scope = TenancyScope(entry.home, entry.user_id, entry.org_id)
            group = groups.setdefault(scope, {})
            if group.setdefault(entry.effect_key, entry) is not entry:
                doubles.append(entry)
        await self._repeated(doubles)
        for scope, group in groups.items():
            try:
                await self._write_group(scope, list(group.values()))
            except HomeUnavailableError:
                for entry in group.values():
                    await self._defer(entry)
            except SQLAlchemyError:
                # Пачка одной компании не должна останавливать пачки остальных.
                for _ in group:
                    self._metrics.lost()
                log.exception(
                    "Пачка строк стоимости не записана", home=scope.home.value, rows=len(group)
                )

    async def _write_group(self, scope: TenancyScope, entries: list[CostEntry]) -> None:
        keys = [BatchKey(entry.effect_key, entry.user_id, entry.org_id) for entry in entries]
        async with self._transactions.begin(scope) as session:
            claimed = await self._batch.claim(session, AI_COST, keys)
            fresh = [entry for entry in entries if entry.effect_key in claimed]
            if fresh:
                await session.execute(insert(ProviderCost).values([row_of(e) for e in fresh]))
                for entry in fresh:
                    await self._settle(session, entry)
                outcomes = {e.effect_key: RecordedCost(cost_id=e.cost_id) for e in fresh}
                await self._batch.complete(session, AI_COST, outcomes)
        # Пометки в Valkey — после коммита: в транзакции внешних вызовов нет (§14 правило 1).
        await self._repeated([entry for entry in entries if entry.effect_key not in claimed])
        if fresh:
            await self._inserted(fresh)

    async def _insert(self, session: AsyncSession, entry: CostEntry) -> RecordedCost:
        await session.execute(insert(ProviderCost).values(row_of(entry)))
        await self._settle(session, entry)
        return RecordedCost(cost_id=entry.cost_id)

    async def _settle(self, session: AsyncSession, entry: CostEntry) -> None:
        settled = SettledCost(
            cost_id=entry.cost_id,
            user_id=entry.user_id,
            org_id=entry.org_id,
            platform_account=entry.platform_account,
            provider=entry.provider,
            model=entry.model,
            feature=entry.feature,
            call_class=entry.call_class,
            origin=entry.origin,
            cost_usd=entry.cost_usd,
            created_at=entry.created_at,
            tokens=(
                entry.input_tokens
                + entry.output_tokens
                + entry.input_audio_tokens
                + entry.output_audio_tokens
                + entry.input_image_tokens
                + entry.output_image_tokens
            ),
            kind=entry.kind,
        )
        for settlement in self._settlements.all():
            await settlement.settle(session, settled)

    async def _defer(self, entry: CostEntry) -> None:
        try:
            await self._sender.send(RECORD_COST, entry)
        except TaskQueueUnavailableError:
            self._metrics.lost()
            log.error(
                "Стоимость вызова потеряна: дом и очередь недоступны",
                home=entry.home.value,
                provider=entry.provider,
                model=entry.model,
                cost_id=str(entry.cost_id),
            )
            return
        self._metrics.deferred()
        log.warning("Стоимость вызова отложена в задачу", home=entry.home.value)


def row_of(entry: CostEntry) -> dict[str, Any]:
    """The column values of an entry's row."""
    values = entry.model_dump(exclude={"home", "cost_id"})
    values["id"] = entry.cost_id
    values["payer"] = "platform" if entry.platform_account else "user"
    return values


def record_cost_handler(writer: CostWriter) -> TaskHandler[CostEntry]:
    """The deferred-record task: the same write, retried while the home is down."""

    async def record_cost(entry: CostEntry) -> None:
        await writer.write(entry)

    return TaskHandler(RECORD_COST, record_cost)
