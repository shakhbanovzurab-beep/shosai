"""The broadcast's door: what its link answers, the waiting room's knocks and a viewer's way
onto the stage (MR-D7, meetings A12b).

The link is a room's invitation, found in either home as a call's is; a room that serves a
call is not a broadcast. The stage gets in before the start, the audience only live, through
the waiting room when the host turned it on, and never past 100 viewers. A session gets a
LiveKit pass with its part's rights — a viewer is hidden and publishes nothing — and a room
pass for the broadcast's routes. An invited viewer steps onto the stage in the same session:
the SFU changes their rights, they do not reconnect.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus

import structlog
from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts import Principal as Person
from shosai.features.meetings.application.broadcast_reads import push, stage_of, stream_of_room
from shosai.features.meetings.application.joining import (
    Entrant,
    FoundRoom,
    JoinDesk,
    JoinRefusedError,
)
from shosai.features.meetings.application.video_server import PassRequest, RoomSpec, VideoServer
from shosai.features.meetings.domain.broadcasts import (
    ON_STAGE,
    SPEAKERS_MAX,
    VIEWERS_MAX,
    BroadcastEntry,
    BroadcastState,
    EntryFacts,
    StageRole,
    entry,
    grants_for,
)
from shosai.features.meetings.domain.joining import JoinRefusal
from shosai.features.meetings.domain.principals import Principal, new_identity, principal_of
from shosai.features.meetings.domain.wire import RoomMarks, room_metadata
from shosai.features.meetings.infrastructure.broadcast_queues import BroadcastQueues, KnockState
from shosai.features.meetings.infrastructure.room_passes import PassHolder, RoomPasses
from shosai.features.meetings.infrastructure.room_records import RoomBanRecord, RoomRecord
from shosai.features.meetings.infrastructure.stream_records import (
    StreamBanRecord,
    StreamMemberRecord,
    StreamRecord,
)

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Ticket:
    """What the link answers someone: where they go, and the passes when they get in."""

    entry: BroadcastEntry
    title: str
    role: StageRole | None
    waiting_room: bool
    identity: str | None = None
    livekit_url: str | None = None
    livekit_token: str | None = None
    room_pass: str | None = None
    knock: str | None = None


class BroadcastDoor:
    """The public way into broadcasts in every home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[JoinDesk, VideoServer, RoomPasses, BroadcastQueues],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._desk, self._server, self._passes, self._queues = services
        self._clock = clock

    async def join(self, token: str, person: Person | None, name: str | None) -> Ticket:
        """What the link answers whoever opens it."""
        found = await self._desk.find(token)
        entrant = await self._desk.entrant(person, name, {})
        room, stream, stage, banned = await self._read(found, entrant.principal.value)
        if banned:
            raise JoinRefusedError(JoinRefusal.REMOVED)
        member = next((item for item in stage if item.principal == entrant.principal.value), None)
        role = None if member is None else StageRole(member.role)
        state = BroadcastState(stream.status)
        viewers = 0
        if role is None and state is BroadcastState.LIVE:
            viewers = await self._viewers(room.lk_room_name, stage)
        answer = entry(EntryFacts(state, role, stream.manual_admit, viewers))
        if answer is BroadcastEntry.WAIT:
            knock = await self._queues.knock(stream.id, entrant.principal.value, entrant.name)
            return self._ticket(stream, answer, None, knock=knock.id)
        if answer not in {BroadcastEntry.STAGE, BroadcastEntry.AUDIENCE}:
            return self._ticket(stream, answer, None)
        on_air = member is None or member.on_air
        return await self._issue(found, (room, stream), entrant, (role, on_air))

    async def knock(self, token: str, knock_id: str) -> Ticket:
        """Whether the waiting room let the knock in; a turned-away knock is `removed`."""
        found = await self._desk.find(token)
        knock = await self._queues.knock_of(knock_id)
        if knock is None:
            raise JoinRefusedError(JoinRefusal.NOT_FOUND)
        room, stream, _stage, banned = await self._read(found, knock.principal)
        if knock.stream_id != stream.id:
            raise JoinRefusedError(JoinRefusal.NOT_FOUND)
        if banned or knock.state is KnockState.DENIED:
            raise JoinRefusedError(JoinRefusal.REMOVED)
        if stream.status == BroadcastState.ENDED.value:
            return self._ticket(stream, BroadcastEntry.ENDED, None)
        if knock.state is KnockState.WAITING:
            return self._ticket(stream, BroadcastEntry.WAIT, None, knock=knock.id)
        entrant = Entrant(Principal(knock.principal), knock.name, {})
        return await self._issue(found, (room, stream), entrant, (None, True))

    async def step_on_stage(self, holder: PassHolder) -> None:
        """An invited viewer takes a place on the stage, in the same session."""
        scope = TenancyScope(holder.home, holder.owner_id, holder.org_id)
        async with self._transactions.begin(scope) as session:
            stream = await stream_of_room(session, holder.room_id, lock=True)
            hand = await self._queues.hand(stream.id, holder.principal)
            if hand is None or not hand.invited:
                raise AppError("not_invited", HTTPStatus.CONFLICT)
            stage = await stage_of(session, stream.id)
            speakers = sum(1 for item in stage if item.role != StageRole.HOST.value)
            if speakers >= min(stream.speaker_limit, SPEAKERS_MAX):
                raise AppError("stage_full", HTTPStatus.CONFLICT)
            if all(item.principal != holder.principal for item in stage):
                session.add(
                    StreamMemberRecord(
                        id=new_id(), stream_id=stream.id, owner_id=holder.owner_id,
                        org_id=holder.org_id, principal=holder.principal,
                        display_name=holder.author, role=StageRole.SPEAKER.value,
                        position=len(stage),
                    )
                )  # fmt: skip
            room = await session.get_one(RoomRecord, holder.room_id)
        await self._queues.lower_hand(stream.id, holder.principal)
        await self._server.set_grants(room.lk_room_name, holder.identity, ON_STAGE)
        await push(self._server, room.lk_room_name, "state")
        log.info("Зритель вышел на сцену", stream_id=str(stream.id))

    async def _read(
        self, found: FoundRoom, principal: str
    ) -> tuple[RoomRecord, StreamRecord, list[StreamMemberRecord], bool]:
        scope = TenancyScope(found.home, found.owner_id, found.org_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            room = await session.get(RoomRecord, found.room_id)
            stream = await session.scalar(
                select(StreamRecord).where(StreamRecord.room_id == found.room_id)
            )
            if room is None or stream is None:
                raise JoinRefusedError(JoinRefusal.NOT_FOUND)
            stage = await stage_of(session, stream.id)
            banned = await session.scalar(
                select(RoomBanRecord.id).where(
                    RoomBanRecord.room_id == room.id, RoomBanRecord.principal == principal
                )
            ) or await session.scalar(
                select(StreamBanRecord.id).where(
                    StreamBanRecord.stream_id == stream.id, StreamBanRecord.principal == principal
                )
            )
        return room, stream, stage, banned is not None

    async def _viewers(self, room_name: str, stage: Sequence[StreamMemberRecord]) -> int:
        """How many people watch: the room's principals that are not on the stage."""
        on_stage = {item.principal for item in stage}
        people = await self._server.participants(room_name)
        principals = {found.value for person in people if (found := principal_of(person.identity))}
        return len(principals - on_stage)

    async def _issue(
        self,
        found: FoundRoom,
        rows: tuple[RoomRecord, StreamRecord],
        entrant: Entrant,
        part: tuple[StageRole | None, bool],
    ) -> Ticket:
        room, stream = rows
        role, on_air = part
        if not await self._server.rooms([room.lk_room_name]):
            metadata = room_metadata(
                room.id, room.owner_id, RoomMarks(notes=False, recording=False)
            )
            capacity = VIEWERS_MAX + SPEAKERS_MAX + 1
            await self._server.create_room(RoomSpec(room.lk_room_name, capacity, metadata))
        identity = new_identity(entrant.principal)
        request = PassRequest(
            room.lk_room_name, identity, entrant.name, grants_for(role, on_air=on_air)
        )
        session = self._server.session_pass(request, self._clock())
        holder = PassHolder(
            room_id=room.id, home=found.home, owner_id=found.owner_id, org_id=found.org_id,
            principal=entrant.principal.value, identity=identity, author=entrant.name,
        )  # fmt: skip
        room_pass = await self._passes.issue(holder)
        log.info("Вход в трансляцию", stream_id=str(stream.id), stage=role is not None)
        entry_kind = BroadcastEntry.STAGE if role is not None else BroadcastEntry.AUDIENCE
        return Ticket(
            entry=entry_kind, title=stream.title, role=role, waiting_room=stream.manual_admit,
            identity=identity, livekit_url=session.url, livekit_token=session.token,
            room_pass=room_pass,
        )  # fmt: skip

    @staticmethod
    def _ticket(
        stream: StreamRecord,
        answer: BroadcastEntry,
        role: StageRole | None,
        knock: str | None = None,
    ) -> Ticket:
        return Ticket(answer, stream.title, role, stream.manual_admit, knock=knock)
