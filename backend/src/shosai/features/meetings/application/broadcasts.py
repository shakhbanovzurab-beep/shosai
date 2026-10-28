"""The host's broadcasts: a new one, its start and its end (MR-D7, meetings A12b).

A paid plan creates a broadcast: a room of its own in the person's Personal space, the
broadcast's row and the host's place on the stage, once per `Idempotency-Key`. Only the host
starts and ends it. The end keeps the draft's order: everyone in the room is told it ended,
the row and the room close for good, then the SFU's room is deleted; an SFU that does not
answer leaves the closed rows and the sweep ends the room it still holds.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import (
    EffectKey,
    EffectLedger,
    EffectScope,
    account_key,
    fingerprint_of,
)
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.identity.contracts import Principal as Person
from shosai.features.meetings.application.broadcast_reads import broadcast_missing, push
from shosai.features.meetings.application.joining import JoinDesk
from shosai.features.meetings.application.rooms import close_room, open_room, rule_failure
from shosai.features.meetings.application.video_server import VideoServer, VideoUnavailableError
from shosai.features.meetings.domain.broadcasts import BroadcastState, StageRole, may_move
from shosai.features.meetings.domain.rooms import RoomRuleError, checked_title
from shosai.features.meetings.infrastructure.room_records import RoomRecord
from shosai.features.meetings.infrastructure.stream_records import StreamMemberRecord, StreamRecord

CREATES: Final = EffectScope("meetings.broadcast_create", timedelta(hours=24))
log = structlog.stdlib.get_logger(__name__)


class NewBroadcastPrint(BaseModel):
    """The print of a "New broadcast" request, for its `Idempotency-Key`."""

    title: str
    waiting_room: bool


class BroadcastMade(BaseModel):
    """The outcome a repeated key answers: the broadcast it made."""

    stream_id: UUID


@dataclass(frozen=True, slots=True)
class BroadcastView:
    """The host's broadcast: its link's token and where it stands."""

    id: UUID
    title: str
    invite_token: str
    state: BroadcastState
    waiting_room: bool


class Broadcasts:
    """The host's broadcasts in every home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[EffectLedger, PortDirectory, VideoServer, JoinDesk],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._effects, self._ports, self._server, self._desk = services
        self._clock = clock

    async def create(
        self, person: Person, title: str, client_key: str, *, waiting_room: bool
    ) -> BroadcastView:
        """A new broadcast with its room and its host, once per key; a paid plan only."""
        try:
            clean = checked_title(title)
        except RoomRuleError as error:
            raise rule_failure(error) from error
        if clean is None:
            raise AppError("title_required", HTTPStatus.UNPROCESSABLE_ENTITY)
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(person.home, person.user_id)
        if not snapshot.paid:
            raise AppError("broadcast_not_in_plan", HTTPStatus.FORBIDDEN)
        host = await self._desk.entrant(person, None, {})
        effect = EffectKey(
            CREATES,
            account_key(person.user_id, client_key),
            fingerprint_of(NewBroadcastPrint(title=clean, waiting_room=waiting_room)),
        )
        async with self._transactions.begin(person.scope()) as session:

            async def first() -> BroadcastMade:
                room = await open_room(session, person, clean, None)
                room.notes_on = False
                stream = StreamRecord(
                    id=new_id(), owner_id=person.user_id, org_id=None, room_id=room.id,
                    title=clean, manual_admit=waiting_room,
                )  # fmt: skip
                session.add(stream)
                await session.flush()
                session.add(
                    StreamMemberRecord(
                        id=new_id(), stream_id=stream.id, owner_id=person.user_id, org_id=None,
                        principal=host.principal.value, display_name=host.name,
                        role=StageRole.HOST.value,
                    )
                )  # fmt: skip
                log.info("Трансляция создана", stream_id=str(stream.id))
                return BroadcastMade(stream_id=stream.id)

            made = await self._effects.once(session, effect, BroadcastMade, first)
            return await self._view(session, person, made.outcome.stream_id)

    async def start(self, person: Person, stream_id: UUID) -> BroadcastView:
        """Put the broadcast on air; the audience may come in from now on."""
        return await self._move(person, stream_id, BroadcastState.LIVE)

    async def end(self, person: Person, stream_id: UUID) -> BroadcastView:
        """End the broadcast for everyone, in the draft's order."""
        async with self._transactions.begin(person.scope(), read_only=True) as session:
            stream = await self._owned(session, person, stream_id)
            room = await session.get_one(RoomRecord, stream.room_id)
        if stream.status != BroadcastState.ENDED.value:
            await push(self._server, room.lk_room_name, "ended")
        view = await self._move(person, stream_id, BroadcastState.ENDED)
        try:
            await self._server.delete_room(room.lk_room_name)
        except VideoUnavailableError:
            log.warning("SFU не удалил комнату законченной трансляции", stream_id=str(stream_id))
        return view

    async def _move(self, person: Person, stream_id: UUID, target: BroadcastState) -> BroadcastView:
        now = self._clock()
        async with self._transactions.begin(person.scope()) as session:
            stream = await self._owned(session, person, stream_id, lock=True)
            room = await session.get_one(RoomRecord, stream.room_id, with_for_update=True)
            current = BroadcastState(stream.status)
            moved = current is not target
            if moved and not may_move(current, target):
                raise AppError("broadcast_ended", HTTPStatus.CONFLICT)
            if moved:
                stream.status, stream.updated_at = target.value, now
                stream.started_at = stream.started_at or now
                if target is BroadcastState.ENDED:
                    stream.ended_at = now
                    await close_room(session, room, now)
                await session.flush()
                log.info(
                    "Трансляция сменила состояние", stream_id=str(stream_id), state=target.value
                )
            view = await self._view(session, person, stream_id)
        if moved and target is BroadcastState.LIVE:
            await push(self._server, room.lk_room_name, "state")
        return view

    @staticmethod
    async def _owned(
        session: AsyncSession, person: Person, stream_id: UUID, *, lock: bool = False
    ) -> StreamRecord:
        statement = select(StreamRecord).where(
            StreamRecord.id == stream_id, StreamRecord.owner_id == person.user_id
        )
        stream = await session.scalar(statement.with_for_update() if lock else statement)
        if stream is None:
            raise broadcast_missing()
        return stream

    async def _view(self, session: AsyncSession, person: Person, stream_id: UUID) -> BroadcastView:
        stream = await self._owned(session, person, stream_id)
        room = await session.get_one(RoomRecord, stream.room_id)
        return BroadcastView(
            id=stream.id, title=stream.title, invite_token=room.invite_token,
            state=BroadcastState(stream.status), waiting_room=stream.manual_admit,
        )  # fmt: skip
