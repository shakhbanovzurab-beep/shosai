"""The sweep of one home, every 300 s as a singleton tick (meetings plan §1.2, MR-D1).

It reads the SFU's rooms once; when the SFU does not answer, it closes nothing and finishes
nothing. Per open room it takes the domain's verdict: a room the SFU holds is in use; a call
live in the rows but gone from the SFU lost its finish, which the sweep writes as the webhook
would; a room empty for an hour since its last call — or since it was opened — closes, unless
its calendar event is still to come. Closed rooms the SFU still holds — an end or an account's
close the SFU missed — are ended in the SFU. The rows are read by the sweep role and written
as each room's owner, in its space.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.meetings.application.calls import Calls
from shosai.features.meetings.application.joining import FoundRoom
from shosai.features.meetings.application.recording import Recordings
from shosai.features.meetings.application.video_server import VideoServer, VideoUnavailableError
from shosai.features.meetings.contracts import PENDING_EVENTS
from shosai.features.meetings.domain.calls import CallState
from shosai.features.meetings.domain.idle import IdleFacts, SweepVerdict, sweep_verdict
from shosai.features.meetings.domain.rooms import ClosedBy, RoomState
from shosai.features.meetings.infrastructure.meetings_metrics import MeetingsMetrics
from shosai.features.meetings.infrastructure.room_records import RoomCallRecord, RoomRecord

log = structlog.stdlib.get_logger(__name__)


class Sweep:
    """The meetings sweep of a home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[VideoServer, Calls, PortDirectory, MeetingsMetrics, Recordings],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._server, self._calls, self._ports, self._metrics, self._recordings = services
        self._clock = clock

    async def run(self, home: Home) -> None:
        """One pass over the home's open rooms and the SFU's rooms."""
        try:
            held = {room.name for room in await self._server.rooms()}
        except VideoUnavailableError:
            held = None
            log.warning("SFU не ответил обходу: ничего не закрывается", home=home.value)
        now = self._clock()
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rooms = (
                await session.scalars(
                    select(RoomRecord).where(RoomRecord.state == RoomState.OPEN.value)
                )
            ).all()
            calls = await self._latest_calls(session, [room.id for room in rooms])
            pending: set[UUID] = set()
            for binding in self._ports.all(PENDING_EVENTS):
                pending |= await binding.pending(session, [room.id for room in rooms], now)
            stale = [] if held is None else (await session.scalars(
                select(RoomRecord.lk_room_name).where(
                    RoomRecord.state == RoomState.CLOSED.value, RoomRecord.lk_room_name.in_(held)
                )
            )).all()  # fmt: skip
        for room in rooms:
            call = calls.get(room.id)
            facts = IdleFacts(
                opened_at=room.created_at,
                sfu_reachable=held is not None,
                in_sfu=held is not None and room.lk_room_name in held,
                call_live=call is not None and call.state == CallState.LIVE.value,
                last_finished_at=None if call is None else call.emptied_at,
                event_pending=room.id in pending,
                broadcast_live=False,
            )
            verdict = sweep_verdict(facts, now)
            self._metrics.swept(verdict)
            await self._act(home, room, (verdict, call), now)
        for lk_room_name in stale:
            await self._end_in_sfu(lk_room_name)
        await self._recordings.reconcile(home, now)

    async def _act(
        self,
        home: Home,
        room: RoomRecord,
        decided: tuple[SweepVerdict, RoomCallRecord | None],
        now: datetime,
    ) -> None:
        verdict, call = decided
        found = FoundRoom(home=home, room_id=room.id, owner_id=room.owner_id, org_id=room.org_id)
        scope = TenancyScope(home, room.owner_id, room.org_id)
        if verdict is SweepVerdict.FINISH_LOST_CALL and call is not None:
            async with self._transactions.begin(scope) as session:
                finished = await self._calls.finish(session, found, call.id, now)
            if finished:
                await self._calls.hand_over(found, call.id)
        if verdict is SweepVerdict.CLOSE:
            async with self._transactions.begin(scope) as session:
                await session.execute(
                    update(RoomRecord)
                    .where(RoomRecord.id == room.id, RoomRecord.state == RoomState.OPEN.value)
                    .values(
                        state=RoomState.CLOSED.value, closed_at=now,
                        closed_by=ClosedBy.IDLE.value, updated_at=now,
                    )
                )  # fmt: skip
            log.info("Комната закрыта обходом", room_id=str(room.id))

    async def _latest_calls(
        self, session: AsyncSession, room_ids: Sequence[UUID]
    ) -> dict[UUID, RoomCallRecord]:
        if not room_ids:
            return {}
        query = (
            select(RoomCallRecord)
            .where(RoomCallRecord.room_id.in_(room_ids))
            .order_by(RoomCallRecord.room_id, RoomCallRecord.started_at.desc())
            .ext(distinct_on(RoomCallRecord.room_id))
        )
        rows = (await session.scalars(query)).all()
        return {row.room_id: row for row in rows}

    async def _end_in_sfu(self, lk_room_name: str) -> None:
        try:
            await self._server.delete_room(lk_room_name)
        except VideoUnavailableError:
            log.warning("SFU не закончил закрытую комнату; повторит следующий обход")
        else:
            log.info("Закрытая комната закончена в SFU обходом", lk_room_name=lk_room_name)
