"""Calls from the SFU's webhooks (meetings plan §3.5 flows 1 and 4).

A webhook names an SFU room by its LiveKit name; the room is found in either home through the
tables' owner's function and its call is written in the owner's scope. The first event of an
SFU room instance opens its call — once per sid, by a unique key — and publishes
`meetings.call.started`; every event folds into the call as the domain says, the same in any
order and under replays; the finish moves it to `ending` once, publishes
`meetings.call.ended` and queues the call's handover. The handover is the task that later
passes the chat, the board and the participants' tracks to notes (B2, B3); it ends the call.
"""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.sender import TaskSender
from shosai.features.meetings.application.handover import HAND_OVER_CALL, CallTask
from shosai.features.meetings.application.joining import FoundRoom
from shosai.features.meetings.application.video_server import SfuWebhook, WebhookKind
from shosai.features.meetings.contracts.events import CallEnded, CallStarted
from shosai.features.meetings.domain.calls import CallState
from shosai.features.meetings.domain.rooms import CEILING_MIN
from shosai.features.meetings.infrastructure.call_records import RoomChatMessageRecord
from shosai.features.meetings.infrastructure.room_records import CEILING_MAX, RoomCallRecord

LOOKUP = text("SELECT room_id, owner_id, org_id FROM meetings_room_by_livekit_name(:name)")
CALL_EVENTS = frozenset(
    {
        WebhookKind.ROOM_STARTED,
        WebhookKind.ROOM_FINISHED,
        WebhookKind.PARTICIPANT_JOINED,
        WebhookKind.PARTICIPANT_LEFT,
        WebhookKind.PARTICIPANT_CONNECTION_ABORTED,
    }
)
log = structlog.stdlib.get_logger(__name__)


class Calls:
    """The calls of rooms in every home, as the SFU reports them."""

    def __init__(
        self,
        transactions: HomeTransactions,
        writers: tuple[EventOutbox, TaskSender],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._outbox, self._tasks = writers
        self._clock = clock

    async def on_webhook(self, webhook: SfuWebhook) -> bool:
        """Fold a verified webhook into its room's call; False when it names no Shosai room."""
        if webhook.kind not in CALL_EVENTS or not webhook.room_sid:
            return False
        found = await self.find(webhook.room_name)
        if found is None:
            return False
        at = webhook.created_at
        scope = TenancyScope(found.home, found.owner_id, found.org_id)
        async with self._transactions.begin(scope) as session:
            call_id = await self._open(session, found, (webhook.room_sid, webhook.ceiling), at)
            await self._seen(session, call_id, at, webhook.participants)
            finished = webhook.kind is WebhookKind.ROOM_FINISHED and await self.finish(
                session, found, call_id, at
            )
        if finished:
            await self.hand_over(found, call_id)
        return True

    async def finish(
        self, session: AsyncSession, found: FoundRoom, call_id: UUID, at: datetime
    ) -> bool:
        """Move a live call to `ending` once and publish its end; False when it was not live."""
        row = (
            await session.execute(
                update(RoomCallRecord)
                .where(RoomCallRecord.id == call_id, RoomCallRecord.state == CallState.LIVE.value)
                .values(state=CallState.ENDING.value, emptied_at=at)
                .returning(RoomCallRecord.started_at, RoomCallRecord.peak_participants)
            )
        ).first()
        if row is None:
            return False
        await self._outbox.add(
            session,
            CallEnded(
                room_id=found.room_id, call_id=call_id, owner_id=found.owner_id,
                org_id=found.org_id, seconds=max(0, int((at - row.started_at).total_seconds())),
                participants=row.peak_participants,
            ),
        )  # fmt: skip
        log.info("Звонок закончен", room_id=str(found.room_id), call_id=str(call_id))
        return True

    async def hand_over(self, found: FoundRoom, call_id: UUID) -> None:
        """Queue the call's handover; a repeat finds it ended and does nothing."""
        task = CallTask(
            home=found.home, user_id=found.owner_id, org_id=found.org_id, call_id=call_id
        )
        await self._tasks.send(HAND_OVER_CALL, task)

    async def ended(self, task: CallTask) -> None:
        """End a finished call once its handover is done; its chat goes with it."""
        async with self._transactions.begin(task.scope()) as session:
            # Чат живёт только звонок: пока заметки его не принимают (B3), он удаляется.
            await session.execute(
                delete(RoomChatMessageRecord).where(RoomChatMessageRecord.call_id == task.call_id)
            )
            await session.execute(
                update(RoomCallRecord)
                .where(
                    RoomCallRecord.id == task.call_id,
                    RoomCallRecord.state == CallState.ENDING.value,
                )
                .values(state=CallState.ENDED.value, ended_at=self._clock())
            )

    async def find(self, lk_room_name: str) -> FoundRoom | None:
        """The room with this LiveKit name in whichever home holds it."""
        answers = await asyncio.gather(
            *(self._lookup(home, lk_room_name) for home in Home), return_exceptions=True
        )
        found = [answer for answer in answers if isinstance(answer, FoundRoom)]
        if found:
            return found[0]
        failures = [answer for answer in answers if isinstance(answer, BaseException)]
        if failures:
            raise failures[0]
        return None

    async def _open(
        self,
        session: AsyncSession,
        found: FoundRoom,
        instance: tuple[str, int | None],
        at: datetime,
    ) -> UUID:
        sid, ceiling = instance
        opened: UUID | None = await session.scalar(
            insert(RoomCallRecord)
            .values(
                id=new_id(),
                room_id=found.room_id,
                owner_id=found.owner_id,
                org_id=found.org_id,
                lk_room_sid=sid,
                state=CallState.LIVE.value,
                started_at=at,
                ceiling=min(max(ceiling or CEILING_MIN, CEILING_MIN), CEILING_MAX),
            )
            .on_conflict_do_nothing(index_elements=["lk_room_sid"])
            .returning(RoomCallRecord.id)
        )
        if opened is not None:
            await self._outbox.add(
                session,
                CallStarted(
                    room_id=found.room_id,
                    call_id=opened,
                    owner_id=found.owner_id,
                    org_id=found.org_id,
                ),
            )
            log.info("Звонок начался", room_id=str(found.room_id), call_id=str(opened))
            return opened
        call_id = await session.scalar(
            select(RoomCallRecord.id).where(RoomCallRecord.lk_room_sid == sid)
        )
        if call_id is None:
            message = "звонок по sid не найден после конфликта вставки"
            raise RuntimeError(message)
        return call_id

    async def _seen(
        self, session: AsyncSession, call_id: UUID, at: datetime, participants: int | None
    ) -> None:
        await session.execute(
            update(RoomCallRecord)
            .where(RoomCallRecord.id == call_id)
            .values(
                started_at=func.least(RoomCallRecord.started_at, at),
                peak_participants=func.greatest(
                    RoomCallRecord.peak_participants, participants or 0
                ),
            )
        )

    async def _lookup(self, home: Home, lk_room_name: str) -> FoundRoom | None:
        try:
            async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
                row = (await session.execute(LOOKUP, {"name": lk_room_name})).first()
        except HomeUnavailableError:
            log.warning("Дом не ответил на поиск комнаты вебхука", home=home.value)
            raise
        if row is None:
            return None
        return FoundRoom(home=home, room_id=row.room_id, owner_id=row.owner_id, org_id=row.org_id)
