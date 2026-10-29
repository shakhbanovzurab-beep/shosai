"""Outlook Calendar on the `CALENDARS` port, over Microsoft Graph v1.0 (plan step 13).

A sync pass is a calendar view's delta over a fixed window — 90 days back, a year ahead —
since Graph v1.0 follows changes only inside a window; it pages by `@odata.nextLink` and ends
with `@odata.deltaLink`, the cursor of the next pass, kept as Graph wrote it. A cursor Graph
forgot is 410, and the calendar syncs from scratch. A change carries the event's
`@odata.etag` in `If-Match`. A push channel is a subscription that lives at most 4 230
minutes and is renewed by watching again; its lifecycle notifications
(`reauthorizationRequired`, `subscriptionRemoved`, `missed`) come to the same address, and a
notification call carries a batch in its body, each item with the subscription's
`clientState` for the calendar slice to check.
"""

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
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
    ProviderCall,
    ProviderRefusedError,
    ProviderResponse,
    ProviderSession,
)
from shosai.features.connectors.infrastructure.providers.outlook_calendar_shapes import (
    calendar_of,
    event_body,
    event_of,
)

GRAPH: Final = "https://graph.microsoft.com/v1.0"
UTC_TIMES: Final = {"Prefer": 'outlook.timezone="UTC"'}
SYNC_BACK: Final = timedelta(days=90)
SYNC_AHEAD: Final = timedelta(days=365)
LONGEST_SUBSCRIPTION: Final = timedelta(minutes=4230)


def _graph(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _checked(response: ProviderResponse) -> dict[str, Any]:
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
    body = response.json() if response.body else {}
    error = body.get("error") if isinstance(body, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    raise ProviderRefusedError(status, code if isinstance(code, str) else None)


def _page_url(page: str | None, first: str) -> str:
    """A page link Graph gave, only if it is Graph's own; else the first page."""
    return page if page and page.startswith(f"{GRAPH}/") else first


def _items(body: dict[str, Any]) -> list[dict[str, Any]]:
    found = body.get("value")
    return [item for item in found if isinstance(item, dict)] if isinstance(found, list) else []


class OutlookCalendar:
    """The calendar adapter of Outlook."""

    async def calendars(self, session: ProviderSession) -> tuple[RemoteCalendar, ...]:
        """Every calendar of the account."""
        found: list[RemoteCalendar] = []
        url: str | None = f"{GRAPH}/me/calendars?$top=100"
        while url:
            body = _checked(
                await session.request(ProviderCall("GET", "calendar.list_calendars", url))
            )
            found.extend(calendar_of(item) for item in _items(body))
            next_link = body.get("@odata.nextLink")
            url = next_link if isinstance(next_link, str) and next_link.startswith(GRAPH) else None
        return tuple(found)

    async def window(self, session: ProviderSession, query: WindowQuery) -> EventPage:
        """Occurrences between two moments, in UTC."""
        first = (
            f"{GRAPH}/me/calendars/{quote(query.calendar_id, safe='')}/calendarView"
            f"?startDateTime={_graph(query.start)}&endDateTime={_graph(query.end)}&$top=100"
        )
        body = _checked(await session.request(ProviderCall(
            "GET", "calendar.list_events", _page_url(query.page, first), headers=UTC_TIMES,
        )))  # fmt: skip
        events = tuple(event_of(item, query.calendar_id) for item in _items(body))
        return EventPage(events, body.get("@odata.nextLink"))

    async def changes(self, session: ProviderSession, query: ChangesQuery) -> EventChanges:
        """One page of the window's delta; the last page names the next pass's cursor."""
        now = datetime.now(UTC)
        first = (
            f"{GRAPH}/me/calendars/{quote(query.calendar_id, safe='')}/calendarView/delta"
            f"?startDateTime={_graph(now - SYNC_BACK)}&endDateTime={_graph(now + SYNC_AHEAD)}"
        )
        url = _page_url(query.page or query.sync_cursor, first)
        body = _checked(await session.request(
            ProviderCall("GET", "calendar.sync_events", url, headers=UTC_TIMES)
        ))  # fmt: skip
        items = _items(body)
        removed = tuple(str(item["id"]) for item in items if "@removed" in item)
        events = tuple(
            event_of(item, query.calendar_id) for item in items if "@removed" not in item
        )
        page = body.get("@odata.nextLink")
        return EventChanges(events, removed, page, None if page else body.get("@odata.deltaLink"))

    async def write(self, session: ProviderSession, write: EventWrite) -> RemoteEvent:
        """Create the event, or change it while its etag is current."""
        url = f"{GRAPH}/me/calendars/{quote(write.calendar_id, safe='')}/events"
        method, headers = "POST", None
        if write.target is not None:
            url = f"{GRAPH}/me/events/{quote(write.target.event_id, safe='')}"
            method = "PATCH"
            headers = {"If-Match": write.target.etag} if write.target.etag else None
        body = _checked(await session.request(ProviderCall(
            method, "calendar.write_event", url, json_body=event_body(write.draft), headers=headers,
        )))  # fmt: skip
        return event_of(body, write.calendar_id)

    async def delete(self, session: ProviderSession, target: EventTarget) -> None:
        """Delete the event while its etag is current; one already gone is deleted."""
        headers = {"If-Match": target.etag} if target.etag else None
        response = await session.request(ProviderCall(
            "DELETE", "calendar.delete_event",
            f"{GRAPH}/me/events/{quote(target.event_id, safe='')}", headers=headers,
        ))  # fmt: skip
        if response.status != HTTPStatus.NOT_FOUND:
            _checked(response)

    async def watch(self, session: ProviderSession, request: WatchRequest) -> WatchChannel:
        """Subscribe to the calendar's events, with lifecycle notifications at the same address."""
        expires = min(request.expires_at, datetime.now(UTC) + LONGEST_SUBSCRIPTION)
        body = _checked(await session.request(ProviderCall(
            "POST", "calendar.watch", f"{GRAPH}/subscriptions", json_body={
                "changeType": "created,updated,deleted", "notificationUrl": request.address,
                "lifecycleNotificationUrl": request.address, "clientState": request.token,
                "resource": f"me/calendars/{request.calendar_id}/events",
                "expirationDateTime": _graph(expires),
            },
        )))  # fmt: skip
        expiration = body.get("expirationDateTime")
        return WatchChannel(
            str(body["id"]), body.get("resource"),
            datetime.fromisoformat(expiration.replace("Z", "+00:00"))
            if isinstance(expiration, str) else None,
        )  # fmt: skip

    async def renew(
        self, session: ProviderSession, channel: WatchChannel, until: datetime
    ) -> WatchChannel | None:
        """Move the subscription's expiry, as a `reauthorizationRequired` event asks."""
        expires = min(until, datetime.now(UTC) + LONGEST_SUBSCRIPTION)
        body = _checked(await session.request(ProviderCall(
            "PATCH", "calendar.renew_watch",
            f"{GRAPH}/subscriptions/{quote(channel.channel_id, safe='')}",
            json_body={"expirationDateTime": _graph(expires)},
        )))  # fmt: skip
        expiration = body.get("expirationDateTime")
        return WatchChannel(
            channel.channel_id, channel.resource_id,
            datetime.fromisoformat(expiration.replace("Z", "+00:00"))
            if isinstance(expiration, str) else expires,
        )  # fmt: skip

    async def stop(self, session: ProviderSession, channel: WatchChannel) -> None:
        """Delete the subscription; one Graph no longer knows is stopped."""
        response = await session.request(ProviderCall(
            "DELETE", "calendar.stop_watch",
            f"{GRAPH}/subscriptions/{quote(channel.channel_id, safe='')}",
        ))  # fmt: skip
        if response.status != HTTPStatus.NOT_FOUND:
            _checked(response)

    def notifications(
        self, headers: Mapping[str, str], body: bytes
    ) -> tuple[CalendarNotification, ...]:
        """Every item of a Graph notification batch: a change or a subscription's lifecycle."""
        del headers
        try:
            batch = json.loads(body) if body else {}
        except ValueError:
            return ()
        items = batch.get("value") if isinstance(batch, dict) else None
        found: list[CalendarNotification] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict) or not isinstance(item.get("subscriptionId"), str):
                continue
            state = item.get("lifecycleEvent") or item.get("changeType")
            found.append(CalendarNotification(
                channel_id=item["subscriptionId"], token=item.get("clientState"),
                state=str(state or "unknown"), resource_id=item.get("resource"),
            ))  # fmt: skip
        return tuple(found)
