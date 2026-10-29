"""Google Calendar on the `CALENDARS` port (API v3, plan step 10).

A sync pass lists a calendar's events with the series as masters (`singleEvents=false`), a
page at a time, every page with the pass's own parameters — the draft dropped them after the
first page — and ends with `nextSyncToken`, the cursor of the next pass; Google forgets a
cursor after some weeks and answers 410, and the calendar then syncs from scratch. A window
for display expands occurrences (`singleEvents=true`). A change carries `If-Match` with the
etag Shosai read: 412 means the event changed at Google. A push channel lives until its
`expiration` and is never renewed, only watched again; stopping one Google no longer knows
(404) is done. A notification is its headers alone.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, Final
from urllib.parse import quote

from shosai.features.connectors.contracts.calendar_errors import (
    CalendarConflictError,
    CalendarCursorExpiredError,
    CalendarEventNotFoundError,
)
from shosai.features.connectors.contracts.calendars import (
    CalendarNotification,
    ChangesQuery,
    EventChanges,
    EventPage,
    EventTarget,
    EventWrite,
    RemoteCalendar,
    RemoteEvent,
    WatchChannel,
    WatchRequest,
    WindowQuery,
)
from shosai.features.connectors.contracts.provider import (
    ProviderBusyError,
    ProviderCall,
    ProviderRefusedError,
    ProviderResponse,
    ProviderSession,
)
from shosai.features.connectors.infrastructure.providers.google_calendar_shapes import (
    calendar_of,
    event_body,
    event_of,
    is_removal,
)

API: Final = "https://www.googleapis.com/calendar/v3"
PAGE_SIZE: Final = "250"
# Google отвечает 403 и такой причиной, когда исчерпана квота человека или проекта.
RATE_REASONS: Final = frozenset({"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"})
BUSY_WAIT_SECONDS: Final = 30


def _calendar(calendar_id: str) -> str:
    return f"{API}/calendars/{quote(calendar_id, safe='')}"


def _reason(response: ProviderResponse) -> str | None:
    try:
        body = response.json()
    except ProviderRefusedError:
        return None
    error = body.get("error") if isinstance(body, dict) else None
    errors = error.get("errors") if isinstance(error, dict) else None
    first = errors[0] if isinstance(errors, list) and errors else None
    reason = first.get("reason") if isinstance(first, dict) else None
    return reason if isinstance(reason, str) else None


def _checked(response: ProviderResponse) -> dict[str, Any]:
    """The JSON object of a success; Google's refusals as the port's errors."""
    status = response.status
    if status == HTTPStatus.NO_CONTENT:
        return {}
    if HTTPStatus.OK <= status < HTTPStatus.MULTIPLE_CHOICES:
        body = response.json()
        if not isinstance(body, dict):
            raise ProviderRefusedError(status, "not_an_object")
        return body
    if status == HTTPStatus.PRECONDITION_FAILED:
        raise CalendarConflictError
    if status == HTTPStatus.GONE:
        raise CalendarCursorExpiredError
    if status == HTTPStatus.NOT_FOUND:
        raise CalendarEventNotFoundError
    reason = _reason(response)
    if status == HTTPStatus.FORBIDDEN and reason in RATE_REASONS:
        raise ProviderBusyError(BUSY_WAIT_SECONDS)
    raise ProviderRefusedError(status, reason)


def _items(body: dict[str, Any]) -> list[dict[str, Any]]:
    items = body.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


class GoogleCalendar:
    """The calendar adapter of Google Calendar."""

    async def calendars(self, session: ProviderSession) -> tuple[RemoteCalendar, ...]:
        """Every calendar of the account's list, page after page."""
        found: list[RemoteCalendar] = []
        page: str | None = None
        while True:
            params = {"maxResults": PAGE_SIZE} | ({"pageToken": page} if page else {})
            body = _checked(await session.request(ProviderCall(
                "GET", "calendar.list_calendars", f"{API}/users/me/calendarList", params=params,
            )))  # fmt: skip
            found.extend(calendar_of(item) for item in _items(body) if "id" in item)
            page = body.get("nextPageToken")
            if not page:
                return tuple(found)

    async def window(self, session: ProviderSession, query: WindowQuery) -> EventPage:
        """Occurrences between two moments, in start order."""
        params = {
            "timeMin": query.start.astimezone(UTC).isoformat(),
            "timeMax": query.end.astimezone(UTC).isoformat(),
            "singleEvents": "true", "orderBy": "startTime", "maxResults": PAGE_SIZE,
        } | ({"pageToken": query.page} if query.page else {})  # fmt: skip
        body = _checked(await session.request(ProviderCall(
            "GET", "calendar.list_events", f"{_calendar(query.calendar_id)}/events", params=params,
        )))  # fmt: skip
        events = tuple(event_of(item, query.calendar_id) for item in _items(body))
        return EventPage(events, body.get("nextPageToken") or None)

    async def changes(self, session: ProviderSession, query: ChangesQuery) -> EventChanges:
        """One page of a sync pass; the last page names the next pass's cursor."""
        params = {"singleEvents": "false", "maxResults": PAGE_SIZE}
        if query.sync_cursor:
            params["syncToken"] = query.sync_cursor
        if query.page:
            params["pageToken"] = query.page
        body = _checked(await session.request(ProviderCall(
            "GET", "calendar.sync_events", f"{_calendar(query.calendar_id)}/events", params=params,
        )))  # fmt: skip
        items = _items(body)
        events = tuple(event_of(item, query.calendar_id) for item in items if not is_removal(item))
        removed = tuple(str(item["id"]) for item in items if is_removal(item))
        page = body.get("nextPageToken") or None
        return EventChanges(events, removed, page, None if page else body.get("nextSyncToken"))

    async def write(self, session: ProviderSession, write: EventWrite) -> RemoteEvent:
        """Create the event, or change it while its etag is current; invitations go out."""
        params = {"sendUpdates": "all" if write.draft.attendees else "none"}
        if write.draft.add_conference:
            params["conferenceDataVersion"] = "1"
        url, method, headers = f"{_calendar(write.calendar_id)}/events", "POST", None
        if write.target is not None:
            url = f"{url}/{quote(write.target.event_id, safe='')}"
            method = "PATCH"
            headers = {"If-Match": write.target.etag} if write.target.etag else None
        body = _checked(await session.request(ProviderCall(
            method, "calendar.write_event", url, params=params, json_body=event_body(write.draft),
            headers=headers,
        )))  # fmt: skip
        return event_of(body, write.calendar_id)

    async def delete(self, session: ProviderSession, target: EventTarget) -> None:
        """Delete the event while its etag is current; one already gone is deleted."""
        url = f"{_calendar(target.calendar_id)}/events/{quote(target.event_id, safe='')}"
        headers = {"If-Match": target.etag} if target.etag else None
        response = await session.request(
            ProviderCall("DELETE", "calendar.delete_event", url, headers=headers)
        )
        if response.status in {HTTPStatus.NOT_FOUND, HTTPStatus.GONE}:
            return
        _checked(response)

    async def watch(self, session: ProviderSession, request: WatchRequest) -> WatchChannel:
        """Open a channel that pushes the calendar's changes until it expires."""
        body = _checked(await session.request(ProviderCall(
            "POST", "calendar.watch", f"{_calendar(request.calendar_id)}/events/watch",
            json_body={
                "id": request.channel_id, "type": "web_hook", "address": request.address,
                "token": request.token,
                "expiration": str(int(request.expires_at.timestamp() * 1000)),
            },
        )))  # fmt: skip
        expiration = body.get("expiration")
        expires_at = (
            datetime.fromtimestamp(int(expiration) / 1000, UTC)
            if isinstance(expiration, str) and expiration.isdigit()
            else None
        )
        resource = body.get("resourceId")
        return WatchChannel(
            str(body.get("id", request.channel_id)),
            resource if isinstance(resource, str) else None, expires_at,
        )  # fmt: skip

    async def renew(
        self, session: ProviderSession, channel: WatchChannel, until: datetime
    ) -> WatchChannel | None:
        """Google renews no channel: the calendar slice watches again before it expires."""
        del session, channel, until
        return None

    async def stop(self, session: ProviderSession, channel: WatchChannel) -> None:
        """Stop a channel; one Google no longer knows has stopped already."""
        response = await session.request(ProviderCall(
            "POST", "calendar.stop_watch", f"{API}/channels/stop",
            json_body={"id": channel.channel_id, "resourceId": channel.resource_id},
        ))  # fmt: skip
        if response.status != HTTPStatus.NOT_FOUND:
            _checked(response)

    def notifications(
        self, headers: Mapping[str, str], body: bytes
    ) -> tuple[CalendarNotification, ...]:
        """Google's push, all in its headers: the channel, its token, the state, the number."""
        del body
        lowered = {key.lower(): value for key, value in headers.items()}
        channel = lowered.get("x-goog-channel-id")
        state = lowered.get("x-goog-resource-state")
        if not channel or not state:
            return ()
        number = lowered.get("x-goog-message-number", "")
        return (CalendarNotification(
            channel_id=channel, token=lowered.get("x-goog-channel-token"), state=state,
            message_number=int(number) if number.isdigit() else None,
            resource_id=lowered.get("x-goog-resource-id"),
        ),)  # fmt: skip
