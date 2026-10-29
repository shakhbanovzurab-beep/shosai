"""Google Calendar's API as recorded answers, behind `CALENDARS` over a connected account.

The double keeps one calendar's events and answers the shapes Google documents: a full sync
in two pages ending with `nextSyncToken` `sync-1`, the changes since `sync-1`, 410 for the
cursor `sync-stale`, 412 for an etag that is not current, a channel that is opened and one
(`gone-channel`) that Google no longer knows.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest_asyncio
from redis.asyncio import Redis

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.calendars import ConnectorCalendars
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.providers.google_calendar import GoogleCalendar
from tests.features.connectors.google_bench import GoogleBench, Person
from tests.features.connectors.provider_sessions import provider_access

PRIMARY = "anna@gmail.com"
SERIES = {
    "kind": "calendar#event", "id": "standup", "etag": '"3181"', "status": "confirmed",
    "summary": "Standup", "htmlLink": "https://calendar.google.com/event?eid=s",
    "start": {"dateTime": "2026-11-02T10:00:00+03:00", "timeZone": "Europe/Moscow"},
    "end": {"dateTime": "2026-11-02T10:15:00+03:00", "timeZone": "Europe/Moscow"},
    "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO,WE"], "updated": "2026-10-27T08:00:00.000Z",
}  # fmt: skip
REVIEW = {
    "id": "review", "etag": '"3182"', "status": "confirmed", "summary": "Design review",
    "start": {"dateTime": "2026-11-03T15:00:00Z"}, "end": {"dateTime": "2026-11-03T16:00:00Z"},
    "hangoutLink": "https://meet.google.com/abc-defg-hij",
    "attendees": [
        {"email": PRIMARY, "self": True, "organizer": True, "responseStatus": "accepted"},
        {"email": "boris@example.com", "displayName": "Boris", "responseStatus": "tentative"},
    ],
}  # fmt: skip
HOLIDAY = {
    "id": "offsite", "etag": '"3183"', "status": "confirmed", "summary": "Offsite",
    "transparency": "transparent", "start": {"date": "2026-11-05"}, "end": {"date": "2026-11-06"},
}  # fmt: skip


def gone(code: int, reason: str) -> httpx.Response:
    """Google's error envelope."""
    return httpx.Response(code, json={"error": {
        "code": code, "message": reason, "errors": [{"domain": "calendar", "reason": reason}],
    }})  # fmt: skip


@dataclass
class CalendarDouble:
    """www.googleapis.com/calendar/v3 for one account."""

    requests: list[tuple[str, str, dict[str, list[str]], Any]] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        """One call to the Calendar API."""
        url = urlsplit(str(request.url))
        query = parse_qs(url.query)
        body = request.read() or b""
        payload: dict[str, Any] = httpx.Response(200, content=body).json() if body else {}
        self.requests.append((request.method, url.path, query, payload))
        path = url.path.removeprefix("/calendar/v3")
        if path in {"/users/me/calendarList", "/channels/stop"} or path.endswith("/watch"):
            return self.channels(path, payload)
        if path.endswith("/events") and request.method == "GET":
            return self.events(query)
        return self.write(request, path, payload)

    def channels(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        """The calendar list, a channel opened, a channel stopped."""
        if path == "/users/me/calendarList":
            return httpx.Response(200, json={"items": [
                {"id": PRIMARY, "summary": PRIMARY, "accessRole": "owner", "primary": True,
                 "timeZone": "Europe/Moscow", "backgroundColor": "#9fe1e7"},
                {"id": "ru.russian#holiday@group.v.calendar.google.com", "summary": "Holidays",
                 "accessRole": "reader"},
            ]})  # fmt: skip
        if path == "/channels/stop":
            channel = str(payload.get("id", ""))
            self.stopped.append(channel)
            return gone(404, "notFound") if channel == "gone-channel" else httpx.Response(204)
        return httpx.Response(200, json={
            "kind": "api#channel", "id": payload["id"], "resourceId": "res-1",
            "resourceUri": "https://www.googleapis.com/calendar/v3/calendars/x/events",
            "expiration": "1793232000000",
        })  # fmt: skip

    def write(self, request: httpx.Request, path: str, payload: dict[str, Any]) -> httpx.Response:
        """A new event, or a change or a deletion checked against the current etag."""
        if path.endswith("/events"):
            return httpx.Response(200, json={**payload, "id": "new-1", "etag": '"4001"',
                                             "status": "confirmed"})  # fmt: skip
        if request.headers.get("If-Match") == '"stale"':
            return gone(412, "conditionNotMet")
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={**REVIEW, **payload, "etag": '"3190"'})

    def events(self, query: dict[str, list[str]]) -> httpx.Response:
        """A window, a full sync in two pages, or the changes since a cursor."""
        if query.get("singleEvents") == ["true"]:
            return httpx.Response(200, json={"items": [REVIEW, HOLIDAY]})
        cursor, page = query.get("syncToken", [None])[0], query.get("pageToken", [None])[0]
        if cursor == "sync-stale":
            return gone(410, "fullSyncRequired")
        if cursor == "sync-1":
            moved = {**REVIEW, "start": {"dateTime": "2026-11-03T16:00:00Z"}, "etag": '"3185"'}
            skipped = {
                "id": "standup_20261104T070000Z",
                "status": "cancelled",
                "recurringEventId": "standup",
                "originalStartTime": {"dateTime": "2026-11-04T10:00:00+03:00"},
            }
            return httpx.Response(200, json={"nextSyncToken": "sync-2", "items": [
                moved, {"id": "offsite", "status": "cancelled"}, skipped,
            ]})  # fmt: skip
        if page is None:
            return httpx.Response(200, json={"items": [SERIES], "nextPageToken": "p2"})
        return httpx.Response(200, json={"items": [REVIEW, HOLIDAY], "nextSyncToken": "sync-1"})


@dataclass(frozen=True, slots=True)
class CalendarBench:
    """`CALENDARS` over a person's connected Google Calendar."""

    calendars: ConnectorCalendars
    api: CalendarDouble
    google: GoogleBench

    async def connected(self, person: Person, app: App = App.GOOGLE_CALENDAR) -> TenancyScope:
        """The person with the app connected."""
        await self.google.connect(person, app)
        return TenancyScope(*person)


@pytest_asyncio.fixture
async def calendar(google: GoogleBench, valkey: Redis) -> AsyncIterator[CalendarBench]:
    """Google Calendar behind `CALENDARS`."""
    api = CalendarDouble()
    async with provider_access(google, valkey, ("www.googleapis.com", api.handle)) as access:
        yield CalendarBench(
            ConnectorCalendars(access, {App.GOOGLE_CALENDAR: GoogleCalendar()}), api, google
        )
