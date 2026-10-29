"""Google Calendar's JSON as the `CALENDARS` port's shapes, and back (API v3).

An event's time is `{dateTime, timeZone}` or an all-day `{date}`; a series is its master with
`recurrence` rules, and a changed or cancelled occurrence names its series in
`recurringEventId`. A cancelled event without a series is a removal; a cancelled occurrence is
an event of its own, timed at its original start, so the calendar knows which occurrence
went. The conference is Meet's `hangoutLink` or a video entry point of `conferenceData`.
"""

import uuid
from datetime import date, datetime
from typing import Any, Final

from shosai.features.connectors.contracts.calendars import (
    Attendee,
    AttendeeResponse,
    CalendarAccess,
    EventDraft,
    EventStatus,
    EventTime,
    RemoteCalendar,
    RemoteEvent,
)
from shosai.features.connectors.contracts.provider import ProviderRefusedError

ACCESS: Final = {
    "owner": CalendarAccess.OWNER, "writer": CalendarAccess.WRITER,
    "reader": CalendarAccess.READER, "freeBusyReader": CalendarAccess.FREE_BUSY,
}  # fmt: skip
RESPONSES: Final = {
    "needsAction": AttendeeResponse.NEEDS_ACTION, "accepted": AttendeeResponse.ACCEPTED,
    "declined": AttendeeResponse.DECLINED, "tentative": AttendeeResponse.TENTATIVE,
}  # fmt: skip


def _text(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    return value if isinstance(value, str) and value else None


def _moment(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def time_of(value: object) -> EventTime:
    """An event time of Google's shape."""
    if isinstance(value, dict):
        if isinstance(value.get("dateTime"), str):
            return EventTime(at=_moment(value["dateTime"]), time_zone=_text(value, "timeZone"))
        if isinstance(value.get("date"), str):
            return EventTime(day=date.fromisoformat(value["date"]))
    raise ProviderRefusedError(200, "event_time")


def calendar_of(item: dict[str, Any]) -> RemoteCalendar:
    """One entry of the calendar list."""
    return RemoteCalendar(
        id=str(item["id"]), name=_text(item, "summaryOverride") or _text(item, "summary") or "",
        access=ACCESS.get(str(item.get("accessRole")), CalendarAccess.READER),
        primary=item.get("primary") is True, time_zone=_text(item, "timeZone"),
        color=_text(item, "backgroundColor"),
    )  # fmt: skip


def _attendee(item: dict[str, Any]) -> Attendee | None:
    email = _text(item, "email")
    if email is None:
        return None
    return Attendee(
        email=email, name=_text(item, "displayName"),
        response=RESPONSES.get(str(item.get("responseStatus")), AttendeeResponse.NEEDS_ACTION),
        organizer=item.get("organizer") is True, optional=item.get("optional") is True,
        is_self=item.get("self") is True,
    )  # fmt: skip


def _conference(item: dict[str, Any]) -> str | None:
    link = _text(item, "hangoutLink")
    if link is not None:
        return link
    data = item.get("conferenceData")
    points = data.get("entryPoints") if isinstance(data, dict) else None
    for point in points if isinstance(points, list) else []:
        if isinstance(point, dict) and point.get("entryPointType") == "video":
            return _text(point, "uri")
    return None


def _attendees(item: dict[str, Any]) -> tuple[Attendee, ...]:
    listed = item.get("attendees")
    if not isinstance(listed, list):
        return ()
    found = (_attendee(entry) for entry in listed if isinstance(entry, dict))
    return tuple(attendee for attendee in found if attendee is not None)


def _recurrence(item: dict[str, Any]) -> tuple[str, ...]:
    rules = item.get("recurrence")
    return tuple(rule for rule in rules if isinstance(rule, str)) if isinstance(rules, list) else ()


def _times(item: dict[str, Any]) -> tuple[EventTime, EventTime, EventTime | None]:
    """Start, end and the original start; a cancelled occurrence has only the last."""
    original = item.get("originalStartTime")
    original_start = time_of(original) if original is not None else None
    if original_start is not None and "start" not in item:
        return original_start, original_start, original_start
    return time_of(item.get("start")), time_of(item.get("end")), original_start


def event_of(item: dict[str, Any], calendar_id: str) -> RemoteEvent:
    """One event of Google's shape."""
    start, end, original_start = _times(item)
    updated = _text(item, "updated")
    return RemoteEvent(
        id=str(item["id"]), calendar_id=calendar_id, etag=_text(item, "etag"),
        status=_status(item.get("status")), title=_text(item, "summary") or "",
        start=start, end=end, description=_text(item, "description"),
        location=_text(item, "location"), attendees=_attendees(item),
        recurrence=_recurrence(item), series_id=_text(item, "recurringEventId"),
        original_start=original_start, conference_url=_conference(item),
        html_link=_text(item, "htmlLink"), busy=item.get("transparency") != "transparent",
        updated_at=_moment(updated) if updated is not None else None,
    )  # fmt: skip


def _status(value: object) -> EventStatus:
    return (
        EventStatus(value)
        if isinstance(value, str) and value in EventStatus
        else EventStatus.CONFIRMED
    )


def is_removal(item: dict[str, Any]) -> bool:
    """A cancelled event that is not an occurrence of a series: the event is gone."""
    return item.get("status") == "cancelled" and not item.get("recurringEventId")


def _time_body(value: EventTime) -> dict[str, str]:
    if value.day is not None:
        return {"date": value.day.isoformat()}
    if value.at is None:
        message = "время события без момента"
        raise ValueError(message)
    body = {"dateTime": value.at.isoformat()}
    if value.time_zone is not None:
        body["timeZone"] = value.time_zone
    return body


def event_body(draft: EventDraft) -> dict[str, Any]:
    """The JSON Shosai sends to create or change an event."""
    body: dict[str, Any] = {
        "summary": draft.title, "start": _time_body(draft.start), "end": _time_body(draft.end),
        "transparency": "opaque" if draft.busy else "transparent",
        "description": draft.description, "location": draft.location,
        "attendees": [{"email": email} for email in draft.attendees],
    }  # fmt: skip
    if draft.recurrence:
        body["recurrence"] = list(draft.recurrence)
    if draft.add_conference:
        body["conferenceData"] = {"createRequest": {
            "requestId": str(uuid.uuid4()), "conferenceSolutionKey": {"type": "hangoutsMeet"},
        }}  # fmt: skip
    return body
