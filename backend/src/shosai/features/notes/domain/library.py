"""The library's small rules: folders, the person's own notes and participants (plan §3.3).

Folders are flat and personal, named 1 to 40 characters, coloured in turn green, violet, red,
blue, amber as the cabinet does (MT-D7). The person's own notes are last-write-wins with a
version that grows by one; the cabinet keeps them to 50 000 characters, the native route
to 256 KiB, and a client the draft did not know writes as `web`. A participant is an
address, normalised, with an optional name; only the ones the person added can be
removed, and a meeting lists at most 100.
"""

import re
import unicodedata
from enum import StrEnum
from typing import Final

FOLDER_NAME_MAX: Final = 40
CABINET_NOTES_MAX_CHARS: Final = 50_000
NATIVE_NOTES_MAX_BYTES: Final = 256 * 1024
EMAIL_MAX: Final = 254
PARTICIPANT_NAME_MAX: Final = 120
PARTICIPANTS_MAX: Final = 100
EMAIL: Final = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class FolderColor(StrEnum):
    """A folder's colour."""

    GREEN = "green"
    VIOLET = "violet"
    RED = "red"
    BLUE = "blue"
    AMBER = "amber"


COLOR_CYCLE: Final = tuple(FolderColor)


class LibraryRule(StrEnum):
    """A rule of the library; the value is the API's error code."""

    FOLDER_NAME_REQUIRED = "folder_name_required"
    FOLDER_NAME_TOO_LONG = "folder_name_too_long"
    NOTES_TOO_LONG = "notes_too_long"
    EMAIL_INVALID = "participant_email_invalid"
    PARTICIPANTS_LIMIT = "participants_limit_reached"


class LibraryRuleError(ValueError):
    """A library rule is broken."""

    def __init__(self, rule: LibraryRule) -> None:
        super().__init__(rule.value)
        self.rule = rule
        self.code = rule.value


class NoteClient(StrEnum):
    """Which client last wrote the person's notes."""

    WEB = "web"
    MACOS = "macos"
    WINDOWS = "windows"


class ParticipantSource(StrEnum):
    """How a participant came to the meeting."""

    ADDED = "added"
    CALENDAR = "calendar"
    SPEAKER = "speaker"


def _clean(raw: str) -> str:
    return " ".join("".join(c for c in raw if unicodedata.category(c) != "Cc").split())


def folder_color(existing: int) -> FolderColor:
    """The colour of a person's next folder when they have `existing` ones."""
    return COLOR_CYCLE[existing % len(COLOR_CYCLE)]


def checked_folder_name(raw: str) -> str:
    """The folder's name as stored, or the rule it breaks."""
    name = _clean(raw)
    if not name:
        raise LibraryRuleError(LibraryRule.FOLDER_NAME_REQUIRED)
    if len(name) > FOLDER_NAME_MAX:
        raise LibraryRuleError(LibraryRule.FOLDER_NAME_TOO_LONG)
    return name


def note_client(raw: str | None) -> NoteClient:
    """The writing client; one the draft did not know (`ios`, anything) writes as `web`."""
    try:
        return NoteClient((raw or "").strip().lower())
    except ValueError:
        return NoteClient.WEB


def checked_notes(markdown: str, *, native: bool) -> str:
    """The notes within their route's cap, else `notes_too_long`."""
    too_long = (
        len(markdown.encode()) > NATIVE_NOTES_MAX_BYTES
        if native
        else len(markdown) > CABINET_NOTES_MAX_CHARS
    )
    if too_long:
        raise LibraryRuleError(LibraryRule.NOTES_TOO_LONG)
    return markdown


def next_version(version: int) -> int:
    """The notes' version after a write; every write counts, as in the draft."""
    return max(version, 0) + 1


def normalized_email(raw: str) -> str:
    """A participant's address, trimmed and lower-cased, or `participant_email_invalid`."""
    email = raw.strip().lower()
    if len(email) > EMAIL_MAX or not EMAIL.fullmatch(email):
        raise LibraryRuleError(LibraryRule.EMAIL_INVALID)
    return email


def participant_name(raw: str | None) -> str | None:
    """A participant's name as stored, if any."""
    name = _clean(raw or "")
    return name[:PARTICIPANT_NAME_MAX] or None


def removable(source: ParticipantSource) -> bool:
    """Whether the person may remove the participant: only the ones they added."""
    return source is ParticipantSource.ADDED


def may_add_participant(count: int) -> bool:
    """Whether a meeting with `count` participants may take one more."""
    return count < PARTICIPANTS_MAX
