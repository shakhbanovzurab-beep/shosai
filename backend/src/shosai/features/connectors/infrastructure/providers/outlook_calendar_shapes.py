"""Microsoft Graph's events as the `CALENDARS` port's shapes, and back (v1.0).

Graph's times are `{dateTime, timeZone}` without an offset; Shosai asks for them in UTC
(`Prefer: outlook.timezone="UTC"`), so a time is read as UTC and an all-day event as its day.
A calendar view expands a series into occurrences, each naming its `seriesMasterId`. A
deleted event in a delta answer is `@removed`. An online meeting is Teams' `joinUrl`.
"""

from datetime import UTC, datetime
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

FREE: Final = frozenset({"free", "workingElsewhere"})
RESPONSES: Final = {
    "none": AttendeeResponse.NEEDS_ACTION, "notResponded": AttendeeResponse.NEEDS_ACTION,
    "accepted": AttendeeResponse.ACCEPTED, "declined": AttendeeResponse.DECLINED,
    "tentativelyAccepted": AttendeeResponse.TENTATIVE, "organizer": AttendeeResponse.ACCEPTED,
}  # fmt: skip


def _text(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    return value if isinstance(value, str) and value else None


def calendar_of(item: dict[str, Any]) -> RemoteCalendar:
    """One of the account's calendars."""
    access = CalendarAccess.WRITER if item.get("canEdit") else CalendarAccess.READER
    if item.get("isDefaultCalendar"):
        access = CalendarAccess.OWNER
    return RemoteCalendar(
        id=str(item["id"]), name=_text(item, "name") or "", access=access,
        primary=item.get("isDefaultCalendar") is True, color=_text(item, "hexColor"),
    )  # fmt: skip


def time_of(value: object, *, all_day: bool) -> EventTime:
    """A Graph time in UTC, or the day of an all-day event."""
    if not isinstance(value, dict) or not isinstance(value.get("dateTime"), str):
        raise ProviderRefusedError(200, "event_time")
    moment = datetime.fromisoformat(value["dateTime"][:26])
    if all_day:
        return EventTime(day=moment.date())
    return EventTime(at=moment.replace(tzinfo=UTC), time_zone=_text(value, "timeZone"))


def _attendee(item: dict[str, Any], organizer: str | None) -> Attendee | None:
    address = item.get("emailAddress")
    email = address.get("address") if isinstance(address, dict) else None
    if not isinstance(email, str) or not email:
        return None
    status = item.get("status")
    response = status.get("response") if isinstance(status, dict) else None
    return Attendee(
        email=email, name=address.get("name") if isinstance(address, dict) else None,
        response=RESPONSES.get(str(response), AttendeeResponse.NEEDS_ACTION),
        organizer=email == organizer, optional=item.get("type") == "optional",
    )  # fmt: skip


def _organizer(item: dict[str, Any]) -> str | None:
    organizer = item.get("organizer")
    address = organizer.get("emailAddress") if isinstance(organizer, dict) else None
    email = address.get("address") if isinstance(address, dict) else None
    return email if isinstance(email, str) else None


def _attendees(item: dict[str, Any]) -> tuple[Attendee, ...]:
    listed = item.get("attendees")
    if not isinstance(listed, list):
        return ()
    organizer = _organizer(item)
    found = (_attendee(entry, organizer) for entry in listed if isinstance(entry, dict))
    return tuple(attendee for attendee in found if attendee is not None)


def _nested(item: dict[str, Any], key: str, field: str) -> str | None:
    value = item.get(key)
    inner = value.get(field) if isinstance(value, dict) else None
    return inner if isinstance(inner, str) and inner else None


def event_of(item: dict[str, Any], calendar_id: str) -> RemoteEvent:
    """One event of Graph's shape."""
    all_day = item.get("isAllDay") is True
    modified = _text(item, "lastModifiedDateTime")
    return RemoteEvent(
        id=str(item["id"]), calendar_id=calendar_id, etag=_text(item, "@odata.etag"),
        status=EventStatus.CANCELLED if item.get("isCancelled") else EventStatus.CONFIRMED,
        title=_text(item, "subject") or "",
        start=time_of(item.get("start"), all_day=all_day),
        end=time_of(item.get("end"), all_day=all_day),
        description=_text(item, "bodyPreview"), location=_nested(item, "location", "displayName"),
        attendees=_attendees(item), series_id=_text(item, "seriesMasterId"),
        conference_url=_nested(item, "onlineMeeting", "joinUrl"),
        html_link=_text(item, "webLink"), busy=item.get("showAs") not in FREE,
        updated_at=datetime.fromisoformat(modified.replace("Z", "+00:00")) if modified else None,
    )  # fmt: skip


def _time_body(value: EventTime) -> dict[str, str]:
    if value.day is not None:
        return {"dateTime": f"{value.day.isoformat()}T00:00:00", "timeZone": "UTC"}
    if value.at is None:
        message = "время события без момента"
        raise ValueError(message)
    return {
        "dateTime": value.at.astimezone(UTC).replace(tzinfo=None).isoformat(),
        "timeZone": "UTC",
    }


def event_body(draft: EventDraft) -> dict[str, Any]:
    """The JSON Shosai sends to create or change an event."""
    body: dict[str, Any] = {
        "subject": draft.title, "start": _time_body(draft.start), "end": _time_body(draft.end),
        "isAllDay": draft.start.day is not None, "showAs": "busy" if draft.busy else "free",
        "body": {"contentType": "text", "content": draft.description or ""},
        "attendees": [
            {"emailAddress": {"address": email}, "type": "required"} for email in draft.attendees
        ],
    }  # fmt: skip
    if draft.location:
        body["location"] = {"displayName": draft.location}
    if draft.add_conference:
        body |= {"isOnlineMeeting": True, "onlineMeetingProvider": "teamsForBusiness"}
    return body
