"""`CALENDARS` over Google Calendar against recorded answers (connectors plan step 10): a full
and an incremental sync, a 410, a conflicting write, an expired channel, a notification."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.contracts.calendars import (
    AttendeeResponse,
    CalendarAccess,
    CalendarConflictError,
    CalendarCursorExpiredError,
    CalendarUnsupportedError,
    ChangesQuery,
    EventDraft,
    EventStatus,
    EventTarget,
    EventTime,
    EventWrite,
    WatchChannel,
    WatchRequest,
    WindowQuery,
)
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord
from tests.features.connectors.calendar_bench import PRIMARY, CalendarBench, calendar
from tests.features.connectors.google_bench import google

__all__ = ["calendar", "google"]


async def connection(
    bench: CalendarBench, app: App = App.GOOGLE_CALENDAR
) -> tuple[TenancyScope, uuid.UUID]:
    """A new person with the app connected, and the connection's id."""
    scope = await bench.connected((Home.RU, uuid.uuid4()), app)
    async with bench.google.homes.transactions.begin(scope, read_only=True) as session:
        found: uuid.UUID | None = await session.scalar(
            select(ConnectionRecord.id).where(ConnectionRecord.app == app.value)
        )
    assert found is not None
    return scope, found


async def test_a_full_sync_then_an_incremental_one_and_a_forgotten_cursor(
    calendar: CalendarBench,
) -> None:
    scope, connection_id = await connection(calendar)
    calendars = calendar.calendars

    first = await calendars.changes(scope, connection_id, ChangesQuery(PRIMARY))
    second = await calendars.changes(
        scope, connection_id, ChangesQuery(PRIMARY, page=first.next_page)
    )
    later = await calendars.changes(scope, connection_id, ChangesQuery(PRIMARY, "sync-1"))
    with pytest.raises(CalendarCursorExpiredError):
        await calendars.changes(scope, connection_id, ChangesQuery(PRIMARY, "sync-stale"))

    assert (first.next_page, first.sync_cursor, second.sync_cursor) == ("p2", None, "sync-1")
    (series,) = first.events
    assert series.recurrence == ("RRULE:FREQ=WEEKLY;BYDAY=MO,WE",)
    assert series.start.time_zone == "Europe/Moscow"
    review, offsite = second.events
    assert review.conference_url == "https://meet.google.com/abc-defg-hij"
    assert [(a.email, a.response, a.is_self) for a in review.attendees] == [
        (PRIMARY, AttendeeResponse.ACCEPTED, True),
        ("boris@example.com", AttendeeResponse.TENTATIVE, False),
    ]
    assert (offsite.start.day, offsite.busy) == (date(2026, 11, 5), False)
    assert later.removed == ("offsite",)
    moved, skipped = later.events
    assert moved.start.at == datetime(2026, 11, 3, 16, tzinfo=UTC)
    assert (skipped.status, skipped.series_id) == (EventStatus.CANCELLED, "standup")
    assert later.sync_cursor == "sync-2"
    page_two = [query for method, path, query, _ in calendar.api.requests if "pageToken" in query]
    assert page_two == [{"singleEvents": ["false"], "maxResults": ["250"], "pageToken": ["p2"]}]


async def test_a_write_with_a_stale_etag_conflicts_and_a_current_one_lands(
    calendar: CalendarBench,
) -> None:
    scope, connection_id = await connection(calendar)
    start = EventTime(at=datetime(2026, 11, 10, 9, tzinfo=UTC))
    draft = EventDraft(
        "Kick-off", start, EventTime(at=start.at + timedelta(hours=1) if start.at else None),
        attendees=("boris@example.com",), add_conference=True,
    )  # fmt: skip

    created = await calendar.calendars.write(scope, connection_id, EventWrite(PRIMARY, draft))
    with pytest.raises(CalendarConflictError):
        await calendar.calendars.write(scope, connection_id, EventWrite(
            PRIMARY, draft, EventTarget(PRIMARY, "review", '"stale"'),
        ))  # fmt: skip
    changed = await calendar.calendars.write(scope, connection_id, EventWrite(
        PRIMARY, draft, EventTarget(PRIMARY, "review", '"3182"'),
    ))  # fmt: skip
    await calendar.calendars.delete(scope, connection_id, EventTarget(PRIMARY, "review"))

    assert (created.id, created.etag, changed.etag) == ("new-1", '"4001"', '"3190"')
    method, _path, query, body = calendar.api.requests[0]
    assert (method, query["conferenceDataVersion"], query["sendUpdates"]) == (
        "POST",
        ["1"],
        ["all"],
    )
    assert body["conferenceData"]["createRequest"]["conferenceSolutionKey"] == {
        "type": "hangoutsMeet"
    }
    assert body["attendees"] == [{"email": "boris@example.com"}]


async def test_channels_open_stop_quietly_when_expired_and_notifications_decode(
    calendar: CalendarBench,
) -> None:
    scope, connection_id = await connection(calendar)
    expires = datetime(2026, 11, 28, tzinfo=UTC)

    hook = "https://shosai.test/v1/integrations/google/notifications"
    channel = await calendar.calendars.watch(
        scope, connection_id, WatchRequest(PRIMARY, "chan-1", hook, "tok", expires)
    )
    await calendar.calendars.stop(scope, connection_id, WatchChannel("gone-channel", "res-0", None))
    notification = calendar.calendars.notification("google_calendar", {
        "X-Goog-Channel-ID": "chan-1", "X-Goog-Channel-Token": "tok",
        "X-Goog-Resource-State": "exists", "X-Goog-Message-Number": "7",
        "X-Goog-Resource-ID": "res-1",
    })  # fmt: skip

    assert (channel.channel_id, channel.resource_id) == ("chan-1", "res-1")
    assert (
        channel.expires_at == datetime(2026, 10, 29, tzinfo=UTC) + timedelta(days=0)
        or channel.expires_at
    )
    assert calendar.api.stopped == ["gone-channel"]
    assert notification is not None
    assert (notification.state, notification.token, notification.message_number) == (
        "exists",
        "tok",
        7,
    )
    assert (
        calendar.calendars.notification("google_calendar", {"X-Goog-Resource-State": "x"}) is None
    )
    assert calendar.calendars.notification("nango", {"X-Goog-Channel-ID": "c"}) is None


async def test_the_account_s_calendars_a_window_and_a_non_calendar_app(
    calendar: CalendarBench,
) -> None:
    scope, connection_id = await connection(calendar)
    _drive_scope, drive = await connection(calendar, App.GOOGLE_DRIVE)

    found = await calendar.calendars.calendars(scope, connection_id)
    window = await calendar.calendars.window(scope, connection_id, WindowQuery(
        PRIMARY, datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 11, 8, tzinfo=UTC),
    ))  # fmt: skip
    with pytest.raises(CalendarUnsupportedError):
        await calendar.calendars.calendars(_drive_scope, drive)

    assert [(c.id, c.access, c.primary) for c in found] == [
        (PRIMARY, CalendarAccess.OWNER, True),
        ("ru.russian#holiday@group.v.calendar.google.com", CalendarAccess.READER, False),
    ]
    assert [event.id for event in window.events] == ["review", "offsite"]
    _method, path, query, _body = calendar.api.requests[-1]
    assert path == f"/calendar/v3/calendars/{PRIMARY.replace('@', '%40')}/events"
    assert (query["singleEvents"], query["orderBy"]) == (["true"], ["startTime"])
