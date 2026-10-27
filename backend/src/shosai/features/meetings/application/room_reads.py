"""The owner's rooms as the section and the room's routes read them (meetings plan §3.3).

A room is read in its owner's transaction: row-level security already hides every other
person's room and every space the owner is not in, and the query asks for the owner's id on
top, so a room nobody owns here is `room_not_found` whichever reason hides it. A room's call
is its call still going on, if any; how many are in it comes from the SFU, and is unknown
(null) rather than a guess when the SFU does not answer.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Table, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import PageRequest
from shosai.features.meetings.application.video_server import VideoServer, VideoUnavailableError
from shosai.features.meetings.contracts import RoomNotFoundError
from shosai.features.meetings.domain.calls import CallState
from shosai.features.meetings.domain.recordings import ACTIVE_STATES
from shosai.features.meetings.domain.rooms import ClosedBy, Room, RoomState
from shosai.features.meetings.infrastructure.call_records import RoomRecordingRecord
from shosai.features.meetings.infrastructure.room_records import RoomCallRecord, RoomRecord


class LivePosition(BaseModel):
    """Where a page of live rooms ended: the call's start and id."""

    started_at: datetime
    call_id: UUID


LIVE_CURSOR: Final = CursorCodec("meetings.live_rooms", LivePosition)
CALLS: Final = cast("Table", RoomCallRecord.__table__)
LIVE_ORDER: Final = Keyset((CALLS.c.started_at, CALLS.c.id), descending=True)


@dataclass(frozen=True, slots=True)
class CallView:
    """The call going on in a room."""

    started_at: datetime
    participants: int | None


@dataclass(frozen=True, slots=True)
class RoomView:
    """A room as its owner reads it."""

    room: Room
    invite_token: str
    created_at: datetime
    call: CallView | None = None


def room_of(record: RoomRecord) -> Room:
    """The domain room of a row."""
    return Room(
        id=record.id,
        owner_id=record.owner_id,
        org_id=record.org_id,
        title=record.title,
        lk_room_name=record.lk_room_name,
        state=RoomState(record.state),
        notes_on=record.notes_on,
        closed_at=record.closed_at,
        closed_by=None if record.closed_by is None else ClosedBy(record.closed_by),
    )


async def owned_room(
    session: AsyncSession, owner_id: UUID, room_id: UUID, *, lock: bool = False
) -> RoomRecord:
    """The owner's room; `RoomNotFoundError` for any other."""
    query = select(RoomRecord).where(RoomRecord.id == room_id, RoomRecord.owner_id == owner_id)
    record = await session.scalar(query.with_for_update() if lock else query)
    if record is None:
        raise RoomNotFoundError
    return record


async def live_call(session: AsyncSession, room_id: UUID) -> RoomCallRecord | None:
    """The room's call that has not finished in the SFU, if any."""
    return await session.scalar(
        select(RoomCallRecord).where(
            RoomCallRecord.room_id == room_id, RoomCallRecord.state == CallState.LIVE.value
        )
    )


async def recording_on(session: AsyncSession, room_id: UUID) -> bool:
    """Whether a video recording of the room is starting, running or ending."""
    active = select(RoomRecordingRecord.id).where(
        RoomRecordingRecord.room_id == room_id,
        RoomRecordingRecord.state.in_([state.value for state in ACTIVE_STATES]),
    )
    return bool(await session.scalar(select(exists(active))))


async def room_view(session: AsyncSession, record: RoomRecord) -> RoomView:
    """The room with its call, the count left for `with_counts`."""
    call = await live_call(session, record.id)
    return RoomView(
        room=room_of(record),
        invite_token=record.invite_token,
        created_at=record.created_at,
        call=None if call is None else CallView(started_at=call.started_at, participants=None),
    )


async def live_rooms(
    session: AsyncSession, owner_id: UUID, org_id: UUID | None, page: PageRequest
) -> tuple[list[RoomView], str | None]:
    """A page of the owner's rooms in the space with a call going on, latest call first."""
    after = None if page.cursor is None else LIVE_CURSOR.decode(page.cursor)
    space = RoomRecord.org_id.is_(None) if org_id is None else RoomRecord.org_id == org_id
    statement = (
        select(RoomCallRecord)
        .join(RoomRecord, RoomCallRecord.room_id == RoomRecord.id)
        .where(
            RoomRecord.owner_id == owner_id,
            RoomRecord.state == RoomState.OPEN.value,
            RoomCallRecord.state == CallState.LIVE.value,
            space,
        )
    )
    position = None if after is None else (after.started_at, after.call_id)
    calls = list(await session.scalars(LIVE_ORDER.page(statement, position, page.limit)))
    shown = calls[: page.limit]
    rooms = {
        room.id: room
        for room in await session.scalars(
            select(RoomRecord).where(RoomRecord.id.in_([call.room_id for call in shown]))
        )
    }
    views = [
        RoomView(
            room=room_of(rooms[call.room_id]),
            invite_token=rooms[call.room_id].invite_token,
            created_at=rooms[call.room_id].created_at,
            call=CallView(started_at=call.started_at, participants=None),
        )
        for call in shown
    ]
    last = shown[-1] if len(calls) > page.limit else None
    cursor = (
        None
        if last is None
        else LIVE_CURSOR.encode(LivePosition(started_at=last.started_at, call_id=last.id))
    )
    return views, cursor


async def with_counts(server: VideoServer, views: Sequence[RoomView]) -> list[RoomView]:
    """The views with how many are in each live call, in one call to the SFU."""
    names = [view.room.lk_room_name for view in views if view.call is not None]
    if not names:
        return list(views)
    try:
        counts = {room.name: room.participants for room in await server.rooms(names)}
    except VideoUnavailableError:
        return list(views)
    return [
        view
        if view.call is None
        else replace(view, call=replace(view.call, participants=counts.get(view.room.lk_room_name)))
        for view in views
    ]
