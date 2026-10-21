"""How the shipped macOS and Windows 1.4.5 clients decode the answers they read.

Identity's (identity step 13) and notes' (notes steps 3 and 21). Each check mirrors the
clients' DTOs field by field — `AuthClient.swift`, `SessionsClient.swift`, `MeetingDTO.swift`,
`MeetingDetailDTO.swift`, `MeetingImport.swift` and `MeetingAudioHTTPClient.swift` in
WhispererKit, `AuthClient.cs`, `SessionsClient.cs` and `MeetingAudioHttpClient.cs` in the
Windows client, as `contracts/draft/consumers.json` points to them. A
field a client requires must be present with its type; an optional one may be missing or
null but never of another type, since one wrong value fails the decoding of the whole body.
"""

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Final

type Body = Mapping[str, object]

# Целое у клиентов — int в Swift и C#: true и false им не подходят, хотя в Python это int.
INTEGER: Final = (int,)
NUMBER: Final = (int, float)


def _typed(name: str, value: object, kinds: tuple[type, ...]) -> object:
    if bool not in kinds:
        assert not isinstance(value, bool), (name, value)
    assert isinstance(value, kinds), (name, value)
    return value


def _required(body: Body, name: str, kinds: tuple[type, ...]) -> object:
    value = body.get(name)
    assert value is not None, (name, body)
    return _typed(name, value, kinds)


def _optional(body: Body, name: str, kinds: tuple[type, ...]) -> object:
    value = body.get(name)
    return None if value is None else _typed(name, value, kinds)


def decode_token_response(body: Body) -> str:
    """`AuthTokenResponse` of `/auth/login` and `/auth/refresh`; the access token."""
    _required(body, "token_type", (str,))
    _required(body, "expires_in", INTEGER)
    _optional(body, "csrf_token", (str,))
    return str(_required(body, "access_token", (str,)))


def decode_desktop_tokens(body: Body) -> tuple[str, str]:
    """`DesktopTokenResponse` of the desktop exchange and refresh; access and refresh tokens."""
    _required(body, "expires_in", INTEGER)
    access = _required(body, "access_token", (str,))
    refresh = _required(body, "refresh_token", (str,))
    return str(access), str(refresh)


def decode_auth_user(body: Body) -> str:
    """`AuthUser` of `/auth/me`: email and role are required on both clients; the email."""
    _required(body, "role", (str,))
    _optional(body, "language", (str,))
    _optional(body, "no_logs", (bool,))
    subscription = _optional(body, "subscription", (dict,))
    if isinstance(subscription, dict):
        _required(subscription, "status", (str,))
        _optional(subscription, "days_left", INTEGER)
        tariff = _optional(subscription, "tariff", (dict,))
        if isinstance(tariff, dict):
            _required(tariff, "code", (str,))
            _required(tariff, "name", (str,))
            _optional(tariff, "minutes_limit", INTEGER)
    quota = _optional(body, "quota", (dict,))
    if isinstance(quota, dict):
        _required(quota, "unlimited", (bool,))
        _required(quota, "exhausted", (bool,))
        _optional(quota, "remaining_minutes", NUMBER)
    features = _optional(body, "features", (dict,))
    if isinstance(features, dict):
        _required(features, "voice_translation", (bool,))
        _optional(features, "teleprompter", (bool,))
    return str(_required(body, "email", (str,)))


def decode_session_start(body: Body) -> str:
    """`POST /v1/sessions` as `SessionsClient` reads its raw JSON: the meeting's `id`."""
    return str(_required(body, "id", (str,)))


def _items(body: Body, name: str, *, required: bool) -> list[object]:
    """A list field; a missing optional one reads as empty."""
    value = _required(body, name, (list,)) if required else _optional(body, name, (list,))
    return list(value) if isinstance(value, list) else []


def _date(body: Body, name: str, *, required: bool) -> datetime | None:
    """An ISO 8601 time with its zone, with or without a fraction, as `APITransport` parses."""
    value = _required(body, name, (str,)) if required else _optional(body, name, (str,))
    if value is None:
        return None
    moment = datetime.fromisoformat(str(value))
    assert moment.tzinfo is not None, (name, value)
    return moment


def _tags(body: Body) -> None:
    for tag in _items(body, "tags", required=False):
        assert isinstance(tag, dict), tag
        _required(tag, "id", (str,))
        _required(tag, "name", (str,))
        _optional(tag, "color", (str,))


def decode_meeting_summary(body: Body) -> uuid.UUID:
    """`MeetingSummary` of the list and of a rename; the meeting's id."""
    meeting_id = uuid.UUID(str(_required(body, "id", (str,))))
    _required(body, "title", (str,))
    _required(body, "status", (str,))
    _date(body, "started_at", required=True)
    _date(body, "ended_at", required=False)
    for name in ("duration_ms", "segments_count", "map_nodes_count"):
        _optional(body, name, INTEGER)
    _optional(body, "folder_id", (str,))
    _tags(body)
    _optional(body, "ephemeral", (bool,))
    _optional(body, "mcp_shared", (bool,))
    hub = _optional(body, "hub_id", (str,))
    if hub is not None:
        uuid.UUID(str(hub))
    _optional(body, "hub_name", (str,))
    return meeting_id


def decode_meeting_detail(body: Body) -> list[str]:
    """`MeetingDetail` of `/full`; the texts of its segments."""
    uuid.UUID(str(_required(body, "id", (str,))))
    _required(body, "title", (str,))
    _required(body, "status", (str,))
    _date(body, "started_at", required=True)
    _date(body, "ended_at", required=False)
    _optional(body, "folder_id", (str,))
    _tags(body)
    _optional(body, "ephemeral", (bool,))
    texts = []
    for segment in _items(body, "segments", required=False):
        assert isinstance(segment, dict), segment
        _required(segment, "id", (str,))
        _required(segment, "speaker", (str,))
        _optional(segment, "speaker_idx", INTEGER)
        _date(segment, "started_at", required=False)
        _optional(segment, "duration_ms", INTEGER)
        _optional(segment, "confidence", NUMBER)
        texts.append(str(_required(segment, "text", (str,))))
    return texts


def decode_meeting_note(body: Body) -> str:
    """`MeetingNote` (synthesised `Decodable`, camelCase keys); the person's draft."""
    uuid.UUID(str(_required(body, "meetingId", (str,))))
    _optional(body, "enhancedMarkdown", (str,))
    for item in _items(body, "actionItems", required=True):
        assert isinstance(item, dict), item
        _required(item, "id", (str,))
        _required(item, "text", (str,))
        _required(item, "done", (bool,))
        _optional(item, "sourceSegmentId", (str,))
    _optional(body, "templateId", (str,))
    _date(body, "updatedAt", required=True)
    _required(body, "version", INTEGER)
    _optional(body, "lastAuthoringClient", (str,))
    draft = body.get("draftMarkdown")
    assert isinstance(draft, str), body
    return draft


def decode_import_job(body: Body) -> str:
    """`MeetingImportJob`; its stage, one of the kit's five or read as `transcribing`."""
    _required(body, "id", (str,))
    _required(body, "fileName", (str,))
    _optional(body, "progress", NUMBER)
    meeting = _optional(body, "meetingId", (str,))
    if meeting is not None:
        uuid.UUID(str(meeting))
    _optional(body, "error", (str,))
    return str(_required(body, "stage", (str,)))


def decode_upload_state(body: Body) -> tuple[str, bool]:
    """The upload's `Wire` of WhispererKit, which Windows reads leniently; run id and done."""
    run_id = str(_required(body, "run_id", (str,)))
    _required(body, "upload_id", (str,))
    _required(body, "part_size", INTEGER)
    received = _items(body, "received", required=True)
    assert all(isinstance(number, int) for number in received), received
    _required(body, "bytes_received", INTEGER)
    completed = body.get("completed")
    assert isinstance(completed, bool), body
    return run_id, completed
