"""`CALENDARS`: a connected calendar account as the calendar slice syncs it (plan §3.3).

The calendar slice keeps its own events and sync state. Through this port it lists the
account's calendars, reads events in a window for display, follows changes since a cursor
(an expired cursor is `CalendarCursorExpiredError` of `calendar_errors`, and the slice syncs
from scratch), writes with the provider's etag (a stale one is `CalendarConflictError`),
opens, renews and stops push channels, and decodes a push call's notifications. Every call
goes through the person's provider session, so quotas, `Retry-After` and refresh apply, and
no token is ever handed out.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Final, Protocol
from uuid import UUID

from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.keys import PortKey


class CalendarAccess(StrEnum):
    """What the account may do in one calendar."""

    OWNER = "owner"
    WRITER = "writer"
    READER = "reader"
    FREE_BUSY = "free_busy"


class EventStatus(StrEnum):
    """An event's state at the provider."""

    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class AttendeeResponse(StrEnum):
    """An attendee's answer to an invitation."""

    NEEDS_ACTION = "needs_action"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"


@dataclass(frozen=True, slots=True)
class EventTime:
    """A moment with its zone, or a whole day for an all-day event."""

    at: datetime | None = None
    day: date | None = None
    time_zone: str | None = None

    def __post_init__(self) -> None:
        if (self.at is None) == (self.day is None):
            message = "время события — либо момент, либо целый день"
            raise ValueError(message)
        if self.at is not None and self.at.tzinfo is None:
            message = "момент события — с часовым поясом"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class Attendee:
    """One invited person."""

    email: str
    name: str | None = None
    response: AttendeeResponse = AttendeeResponse.NEEDS_ACTION
    organizer: bool = False
    optional: bool = False
    # Это сам владелец подключения.
    is_self: bool = False


@dataclass(frozen=True, slots=True)
class RemoteCalendar:
    """One calendar of the account."""

    id: str
    name: str
    access: CalendarAccess
    primary: bool = False
    time_zone: str | None = None
    color: str | None = None


@dataclass(frozen=True, slots=True)
class RemoteEvent:
    """One event as the provider holds it; a series carries its recurrence rules."""

    id: str
    calendar_id: str
    etag: str | None
    status: EventStatus
    title: str
    start: EventTime
    end: EventTime
    description: str | None = None
    location: str | None = None
    attendees: tuple[Attendee, ...] = ()
    recurrence: tuple[str, ...] = ()
    # Изменённый экземпляр серии: её id и исходное начало экземпляра.
    series_id: str | None = None
    original_start: EventTime | None = None
    conference_url: str | None = None
    html_link: str | None = None
    busy: bool = True
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class EventDraft:
    """What Shosai writes into an event; a conference is asked for, never invented."""

    title: str
    start: EventTime
    end: EventTime
    description: str | None = None
    location: str | None = None
    attendees: tuple[str, ...] = ()
    recurrence: tuple[str, ...] = ()
    add_conference: bool = False
    busy: bool = True


@dataclass(frozen=True, slots=True)
class EventPage:
    """A page of events and the cursor of the next page."""

    events: tuple[RemoteEvent, ...]
    next_page: str | None = None


@dataclass(frozen=True, slots=True)
class EventChanges:
    """A page of changes: events changed, ids removed, and the cursors to go on.

    `next_page` continues this pass; on the last page it is None and `sync_cursor` is the
    cursor of the next pass.
    """

    events: tuple[RemoteEvent, ...]
    removed: tuple[str, ...]
    next_page: str | None = None
    sync_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class WatchRequest:
    """Where the provider should push changes of one calendar, and the token it sends back."""

    calendar_id: str
    channel_id: str
    address: str
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class WatchChannel:
    """An open push channel; a provider without renewal is watched again before it expires."""

    channel_id: str
    resource_id: str | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class CalendarNotification:
    """A push notification: which channel, its token to check, and what happened."""

    channel_id: str
    token: str | None
    # Google: sync, exists, not_exists. Microsoft: created, updated, deleted — или событие жизни
    # подписки: reauthorizationRequired, subscriptionRemoved, missed.
    state: str
    message_number: int | None = None
    resource_id: str | None = None
    extra: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WindowQuery:
    """Events of one calendar between two moments, a page at a time."""

    calendar_id: str
    start: datetime
    end: datetime
    page: str | None = None


@dataclass(frozen=True, slots=True)
class ChangesQuery:
    """One page of a sync pass: from scratch without a cursor, else since it."""

    calendar_id: str
    sync_cursor: str | None = None
    page: str | None = None


@dataclass(frozen=True, slots=True)
class EventTarget:
    """One event, with the etag Shosai last read where the provider keeps one."""

    calendar_id: str
    event_id: str
    etag: str | None = None


@dataclass(frozen=True, slots=True)
class EventWrite:
    """A new event without a target, or a change of the target's event."""

    calendar_id: str
    draft: EventDraft
    target: EventTarget | None = None


class Calendars(Protocol):
    """One port for every calendar provider, chosen by the connection's app."""

    async def calendars(
        self, scope: TenancyScope, connection_id: UUID
    ) -> tuple[RemoteCalendar, ...]:
        """The account's calendars."""
        ...

    async def window(
        self, scope: TenancyScope, connection_id: UUID, query: WindowQuery
    ) -> EventPage:
        """Events of one calendar in a time window, each occurrence of a series apart."""
        ...

    async def changes(
        self, scope: TenancyScope, connection_id: UUID, query: ChangesQuery
    ) -> EventChanges:
        """Changes since a sync cursor, or the whole calendar without one."""
        ...

    async def write(
        self, scope: TenancyScope, connection_id: UUID, write: EventWrite
    ) -> RemoteEvent:
        """Create an event, or change one whose etag is still current."""
        ...

    async def delete(self, scope: TenancyScope, connection_id: UUID, target: EventTarget) -> None:
        """Delete an event; one already gone counts as deleted."""
        ...

    async def watch(
        self, scope: TenancyScope, connection_id: UUID, request: WatchRequest
    ) -> WatchChannel:
        """Open a push channel on one calendar."""
        ...

    async def renew(
        self, scope: TenancyScope, connection_id: UUID, channel: WatchChannel, until: datetime
    ) -> WatchChannel | None:
        """Extend a push channel; None for a provider that cannot, whose channel is watched
        again (Google)."""
        ...

    async def stop(self, scope: TenancyScope, connection_id: UUID, channel: WatchChannel) -> None:
        """Close a push channel; one already expired counts as closed."""
        ...

    def notifications(
        self, app: str, headers: Mapping[str, str], body: bytes
    ) -> tuple[CalendarNotification, ...]:
        """A push call's notifications: Google's one in its headers, Microsoft's batch in its
        body; none when the call is not a notification. Microsoft's validation handshake
        (`?validationToken=`) is answered by the receiving route itself."""
        ...


CALENDARS: Final = PortKey[Calendars]("connectors.calendars")
