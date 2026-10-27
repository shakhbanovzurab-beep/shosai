"""What other slices may use of the meetings slice (meetings plan §3.2).

Calendar makes the room of an event it schedules through `RoomLinks` and reads its link and
state (B5). Meetings asks every slice that schedules rooms, through `PendingEvents`, whether
a room's event is still to come, so the sweep never closes it before; until calendar binds
it nobody answers and no event is pending. The events are in `contracts.events`.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.errors import AppError
from shosai.core.ports.keys import Cardinality, PortKey
from shosai.features.meetings.domain.rooms import RoomState

__all__ = [
    "PENDING_EVENTS",
    "ROOM_LINKS",
    "PendingEvents",
    "RoomLink",
    "RoomLinks",
    "RoomNotFoundError",
    "RoomState",
]


class RoomNotFoundError(AppError):
    """No such room the caller may use: missing or someone else's (404)."""

    def __init__(self) -> None:
        super().__init__("room_not_found", HTTPStatus.NOT_FOUND)


@dataclass(frozen=True, slots=True)
class RoomLink:
    """A room as an invitation names it: its id, its link and whether it still admits."""

    room_id: UUID
    # Полная ссылка `https://…/meet/{token}`: её кладут в письмо и в событие календаря.
    url: str
    state: RoomState


class RoomLinks(Protocol):
    """The rooms of scheduled events, made for the event's owner; bound by meetings."""

    async def open_for_event(
        self,
        session: AsyncSession,
        owner_id: UUID,
        org_id: UUID | None,
        event_ref: str,
        title: str | None,
    ) -> RoomLink:
        """The room of the event, made once per `event_ref` in the owner's scope and home."""
        ...

    async def link(self, session: AsyncSession, owner_id: UUID, room_id: UUID) -> RoomLink:
        """The owner's room's link and state; `RoomNotFoundError` for any other room."""
        ...


class PendingEvents(Protocol):
    """Whether a room's scheduled event is still to come; bound by calendar (B5)."""

    async def pending(
        self, session: AsyncSession, room_ids: Collection[UUID], now: datetime
    ) -> frozenset[UUID]:
        """The rooms among `room_ids` whose event has not ended at `now`."""
        ...


ROOM_LINKS: Final = PortKey[RoomLinks]("meetings.room_links")
# Отвечать может любой срез, который планирует комнаты; без привязок — ни одного события.
PENDING_EVENTS: Final = PortKey[PendingEvents]("meetings.pending_events", Cardinality.MANY)
