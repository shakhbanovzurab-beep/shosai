"""The owner's rooms: open, list the live ones, read, rename, switch notes, end (meetings A4).

"New meeting" opens a room in Personal or a workspace the person is an active member of, once
per `Idempotency-Key`, and its link is the invitation. Only the owner reads and changes a room;
any other room is `room_not_found`. A room is written in a transaction of its own space. The
notes switch changes the marks everyone in a live call sees: the SFU's metadata changes first,
so a mark never says less than what runs. Ending closes the row for good, then ends the call
in the SFU; a room the SFU could not end is still closed, and its link answers that the
meeting has ended.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog
from pydantic import BaseModel
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
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.pagination.page import PageRequest
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.room_reads import (
    RoomView,
    live_call,
    live_rooms,
    owned_room,
    recording_on,
    room_view,
    with_counts,
)
from shosai.features.meetings.application.video_server import VideoServer, VideoUnavailableError
from shosai.features.meetings.domain.invites import new_invite_token
from shosai.features.meetings.domain.rooms import (
    ClosedBy,
    RoomRuleError,
    RoomState,
    checked_title,
    new_livekit_name,
)
from shosai.features.meetings.domain.wire import RoomMarks, room_metadata
from shosai.features.meetings.infrastructure.room_records import RoomRecord
from shosai.features.workspaces.contracts import MEMBERSHIP_READER

ROOM_CREATES: Final = EffectScope("meetings.room_create", timedelta(hours=24))
log = structlog.stdlib.get_logger(__name__)


class NewRoomPrint(BaseModel):
    """The print of a "New meeting" request, for its `Idempotency-Key`."""

    title: str | None
    workspace_id: UUID | None


class RoomMade(BaseModel):
    """The outcome a repeated key answers: the room it made."""

    room_id: UUID


@dataclass(frozen=True, slots=True)
class RoomChange:
    """A new title (empty clears it) and the notes switch; None leaves each as it is."""

    title: str | None = None
    notes_on: bool | None = None


def rule_failure(error: RoomRuleError) -> AppError:
    """The API's error of a broken room rule."""
    status = HTTPStatus.CONFLICT if error.code == "room_closed" else HTTPStatus.UNPROCESSABLE_ENTITY
    return AppError(error.code, status)


class RoomBook:
    """The owner's rooms in their home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        writers: tuple[EffectLedger, PortDirectory],
        server: VideoServer,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._effects, self._ports = writers
        self._server = server
        self._clock = clock

    async def create(
        self, principal: Principal, title: str | None, workspace_id: UUID | None, client_key: str
    ) -> RoomView:
        """A new open room, once per key."""
        try:
            clean = checked_title(title)
        except RoomRuleError as error:
            raise rule_failure(error) from error
        scope = TenancyScope(principal.home, principal.user_id, workspace_id)
        effect = EffectKey(
            ROOM_CREATES,
            account_key(principal.user_id, client_key),
            fingerprint_of(NewRoomPrint(title=clean, workspace_id=workspace_id)),
        )
        async with self._transactions.begin(scope) as session:
            if workspace_id is not None:
                await self._member_of(session, principal, workspace_id)

            async def first() -> RoomMade:
                record = RoomRecord(
                    id=new_id(), owner_id=principal.user_id, org_id=workspace_id, title=clean,
                    lk_room_name=new_livekit_name(), invite_token=new_invite_token(),
                )  # fmt: skip
                session.add(record)
                await session.flush()
                log.info("Комната открыта", room_id=str(record.id), user_id=str(principal.user_id))
                return RoomMade(room_id=record.id)

            made = await self._effects.once(session, effect, RoomMade, first)
            record = await owned_room(session, principal.user_id, made.outcome.room_id)
            return await room_view(session, record)

    async def live(
        self, principal: Principal, workspace_id: UUID | None, page: PageRequest
    ) -> tuple[list[RoomView], str | None]:
        """A page of the person's rooms in the space with a call going on."""
        scope = TenancyScope(principal.home, principal.user_id, workspace_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            if workspace_id is not None:
                await self._member_of(session, principal, workspace_id)
            views, cursor = await live_rooms(session, principal.user_id, workspace_id, page)
        return await with_counts(self._server, views), cursor

    async def read(self, principal: Principal, room_id: UUID) -> RoomView:
        """The person's room with its call, if one goes on."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            view = await room_view(session, await owned_room(session, principal.user_id, room_id))
        return (await with_counts(self._server, [view]))[0]

    async def change(self, principal: Principal, room_id: UUID, change: RoomChange) -> RoomView:
        """Rename the room or switch its notes; a closed room is not changed."""
        space = await self._space_of(principal, room_id)
        scope = TenancyScope(principal.home, principal.user_id, space)
        async with self._transactions.begin(scope) as session:
            record = await owned_room(session, principal.user_id, room_id, lock=True)
            if record.state != RoomState.OPEN.value:
                raise AppError("room_closed", HTTPStatus.CONFLICT)
            if change.title is not None:
                try:
                    record.title = checked_title(change.title)
                except RoomRuleError as error:
                    raise rule_failure(error) from error
            if change.notes_on is not None and change.notes_on != record.notes_on:
                if await live_call(session, room_id) is not None:
                    marks = RoomMarks(
                        notes=change.notes_on, recording=await recording_on(session, room_id)
                    )
                    await self._server.set_metadata(
                        record.lk_room_name, room_metadata(record.id, marks)
                    )
                record.notes_on = change.notes_on
            record.updated_at = self._clock()
            await session.flush()
            return await room_view(session, record)

    async def end(self, principal: Principal, room_id: UUID) -> RoomView:
        """Close the room for good, then end its call in the SFU; a closed room answers as is."""
        space = await self._space_of(principal, room_id)
        scope = TenancyScope(principal.home, principal.user_id, space)
        async with self._transactions.begin(scope) as session:
            record = await owned_room(session, principal.user_id, room_id, lock=True)
            if record.state == RoomState.OPEN.value:
                now = self._clock()
                record.state, record.closed_at = RoomState.CLOSED.value, now
                record.closed_by, record.updated_at = ClosedBy.OWNER.value, now
                await session.flush()
                log.info("Комната закрыта владельцем", room_id=str(room_id))
            view = await room_view(session, record)
        await self._end_in_sfu(record.lk_room_name)
        return view

    async def _member_of(
        self, session: AsyncSession, principal: Principal, workspace_id: UUID
    ) -> None:
        memberships = await self._ports.get(MEMBERSHIP_READER).active(session, principal.user_id)
        if workspace_id not in {membership.org_id for membership in memberships}:
            raise AppError("workspace_not_found", HTTPStatus.NOT_FOUND)

    async def _end_in_sfu(self, lk_room_name: str) -> None:
        try:
            await self._server.delete_room(lk_room_name)
        except VideoUnavailableError:
            # Строка уже закрыта: обход сверит SFU с закрытыми комнатами (A5).
            log.warning("SFU не закончил комнату; её закончит обход", lk_room_name=lk_room_name)

    async def _space_of(self, principal: Principal, room_id: UUID) -> UUID | None:
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return (await owned_room(session, principal.user_id, room_id)).org_id
