"""The broadcast's stage and queues over its routes (MR-D7, meetings A12b).

Everyone with the room's pass reads the state; the host and co-hosts also see the raised
hands and the waiting room. A viewer raises a hand; the host or a co-host invites them to
the stage or declines, lets a knock in or turns it away, takes a speaker off air and back,
or off the stage; only the host names co-hosts, and nobody changes the host. Rights change
in the SFU for the speaker's live sessions, and every change is pushed on topic `stream` so
the room reads its state again. A viewer count the SFU cannot give is unknown, not zero.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Literal
from uuid import UUID

from sqlalchemy import delete

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.application.broadcast_reads import (
    not_allowed,
    push,
    role_of,
    sessions_of,
    stage_of,
    stream_of_room,
)
from shosai.features.meetings.application.video_server import VideoServer, VideoUnavailableError
from shosai.features.meetings.domain.broadcasts import (
    AUDIENCE,
    BroadcastState,
    StageRole,
    grants_for,
    may_manage_cohosts,
    may_moderate,
)
from shosai.features.meetings.domain.joining import Grants
from shosai.features.meetings.domain.principals import principal_of
from shosai.features.meetings.infrastructure.broadcast_queues import BroadcastQueues, Hand, Knock
from shosai.features.meetings.infrastructure.room_passes import PassHolder
from shosai.features.meetings.infrastructure.room_records import RoomRecord
from shosai.features.meetings.infrastructure.stream_records import StreamMemberRecord

type OwnHand = Literal["down", "raised", "invited"]


@dataclass(frozen=True, slots=True)
class Seat:
    """A place on the stage and the session that holds it now, if any."""

    principal: str
    identity: str | None
    name: str
    role: StageRole
    on_air: bool


@dataclass(frozen=True, slots=True)
class BroadcastStateView:
    """The broadcast as one of its people sees it."""

    status: BroadcastState
    title: str
    role: StageRole | None
    members: list[Seat]
    viewers: int | None
    waiting_room: bool
    hands: list[Hand]
    admissions: list[Knock]
    hand: OwnHand
    started_at: datetime | None


@dataclass(frozen=True, slots=True)
class SeatChange:
    """What a moderator changes about a place: on air or not, co-host or speaker."""

    on_air: bool | None = None
    role: StageRole | None = None


class BroadcastStage:
    """The stage and the queues of broadcasts in every home."""

    def __init__(
        self, transactions: HomeTransactions, services: tuple[VideoServer, BroadcastQueues]
    ) -> None:
        self._transactions = transactions
        self._server, self._queues = services

    async def state(self, holder: PassHolder) -> BroadcastStateView:
        """The broadcast's state; the queues only for the host and co-hosts."""
        async with self._transactions.begin(_scope(holder), read_only=True) as session:
            stream = await stream_of_room(session, holder.room_id)
            stage = await stage_of(session, stream.id)
            room = await session.get_one(RoomRecord, holder.room_id)
        role = role_of(stage, holder.principal)
        try:
            identities = [
                person.identity for person in await self._server.participants(room.lk_room_name)
            ]
        except VideoUnavailableError:
            identities = None
        seats = [_seat(member, identities or []) for member in stage]
        moderates = may_moderate(role)
        own = await self._queues.hand(stream.id, holder.principal)
        return BroadcastStateView(
            status=BroadcastState(stream.status), title=stream.title, role=role, members=seats,
            viewers=None if identities is None else _viewers(identities, stage),
            waiting_room=stream.manual_admit,
            hands=await self._queues.hands(stream.id) if moderates else [],
            admissions=await self._queues.waiting(stream.id) if moderates else [],
            hand="down" if own is None else ("invited" if own.invited else "raised"),
            started_at=stream.started_at,
        )  # fmt: skip

    async def raise_hand(self, holder: PassHolder, *, raised: bool) -> None:
        """A viewer asks to speak, or stops asking."""
        stream_id, room_name, role, live = await self._read(holder)
        if role is not None:
            raise AppError("on_stage", HTTPStatus.CONFLICT)
        if raised and not live:
            raise AppError("broadcast_not_live", HTTPStatus.CONFLICT)
        if raised:
            hand = Hand(
                holder.principal, holder.identity, holder.author, datetime.now(UTC), invited=False
            )
            await self._queues.raise_hand(stream_id, hand)
        else:
            await self._queues.lower_hand(stream_id, holder.principal)
        await push(self._server, room_name, "state")

    async def answer_hand(self, holder: PassHolder, principal: str, *, invite: bool) -> None:
        """Invite the hand's viewer to the stage, or decline the hand."""
        stream_id, room_name, role, _live = await self._read(holder)
        if not may_moderate(role):
            raise not_allowed()
        if invite and not await self._queues.invite(stream_id, principal):
            raise AppError("hand_not_found", HTTPStatus.NOT_FOUND)
        if not invite:
            await self._queues.lower_hand(stream_id, principal)
        await push(self._server, room_name, "state")

    async def admit(self, holder: PassHolder, knock_id: str, *, admitted: bool) -> None:
        """Let a knock in, or turn it away."""
        stream_id, room_name, role, _live = await self._read(holder)
        if not may_moderate(role):
            raise not_allowed()
        if not await self._queues.answer(stream_id, knock_id, admitted=admitted):
            raise AppError("knock_not_found", HTTPStatus.NOT_FOUND)
        await push(self._server, room_name, "state")

    async def change_seat(self, holder: PassHolder, principal: str, change: SeatChange) -> None:
        """Take a speaker off air or back, or name or unname a co-host."""
        async with self._transactions.begin(_scope(holder)) as session:
            stream = await stream_of_room(session, holder.room_id, lock=True)
            stage = await stage_of(session, stream.id)
            target = self._target(stage, holder.principal, principal)
            if change.role is not None:
                if (
                    not may_manage_cohosts(role_of(stage, holder.principal))
                    or change.role is StageRole.HOST
                ):
                    raise not_allowed()
                target.role = change.role.value
            if change.on_air is not None:
                target.on_air = change.on_air
            target.updated_at = datetime.now(UTC)
            grants = grants_for(StageRole(target.role), on_air=target.on_air)
            room = await session.get_one(RoomRecord, holder.room_id)
        await self._regrant(room.lk_room_name, principal, grants)

    async def remove_seat(self, holder: PassHolder, principal: str) -> None:
        """Take someone off the stage; their sessions go back to the audience."""
        async with self._transactions.begin(_scope(holder)) as session:
            stream = await stream_of_room(session, holder.room_id, lock=True)
            stage = await stage_of(session, stream.id)
            target = self._target(stage, holder.principal, principal)
            await session.execute(
                delete(StreamMemberRecord).where(StreamMemberRecord.id == target.id)
            )
            room = await session.get_one(RoomRecord, holder.room_id)
        await self._regrant(room.lk_room_name, principal, AUDIENCE)

    async def _regrant(self, room_name: str, principal: str, grants: Grants) -> None:
        try:
            identities = [person.identity for person in await self._server.participants(room_name)]
        except VideoUnavailableError:
            identities = []
        for identity in sessions_of(identities, principal):
            await self._server.set_grants(room_name, identity, grants)
        await push(self._server, room_name, "state")

    @staticmethod
    def _target(
        stage: list[StreamMemberRecord], moderator: str, principal: str
    ) -> StreamMemberRecord:
        if not may_moderate(role_of(stage, moderator)):
            raise not_allowed()
        target = next((item for item in stage if item.principal == principal), None)
        if target is None:
            raise AppError("member_not_found", HTTPStatus.NOT_FOUND)
        if target.role == StageRole.HOST.value:
            raise not_allowed()
        return target

    async def _read(self, holder: PassHolder) -> tuple[UUID, str, StageRole | None, bool]:
        async with self._transactions.begin(_scope(holder), read_only=True) as session:
            stream = await stream_of_room(session, holder.room_id)
            stage = await stage_of(session, stream.id)
            room = await session.get_one(RoomRecord, holder.room_id)
        live = stream.status == BroadcastState.LIVE.value
        return stream.id, room.lk_room_name, role_of(stage, holder.principal), live


def _scope(holder: PassHolder) -> TenancyScope:
    return TenancyScope(holder.home, holder.owner_id, holder.org_id)


def _seat(member: StreamMemberRecord, identities: list[str]) -> Seat:
    live = sessions_of(identities, member.principal)
    return Seat(
        principal=member.principal, identity=live[0] if live else None, name=member.display_name,
        role=StageRole(member.role), on_air=member.on_air,
    )  # fmt: skip


def _viewers(identities: list[str], stage: list[StreamMemberRecord]) -> int:
    on_stage = {item.principal for item in stage}
    principals = {found.value for identity in identities if (found := principal_of(identity))}
    return len(principals - on_stage)
