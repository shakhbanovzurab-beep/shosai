"""A room: the place "New meeting" opens, reached by its one link (meetings plan §3.4, MR-D1).

A room is open until its owner ends it, an operator closes it, its owner's account goes, or
it stays empty for an hour; a closed room never opens again, and its link says the meeting
has ended. Its title is optional: an untitled room is named by whoever shows it. The
participant ceiling is the owner's plan value capped by the platform's (MR-D2).
"""

import re
import secrets
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

TITLE_MAX: Final = 200
# Имя комнаты в LiveKit: «r-» и hex; у перенесённых комнат черновика — их имя как есть (R1).
LIVEKIT_NAME: Final = re.compile(r"r-[0-9a-f]{8,64}")
LIVEKIT_NAME_BYTES: Final = 8
# Меньше двоих — не звонок: тариф с меньшим значением всё равно пускает двоих.
CEILING_MIN: Final = 2
# Потолок платформы по умолчанию (MR-D2); стейджинг задаёт 4 настройкой.
PLATFORM_CEILING: Final = 50


class RoomState(StrEnum):
    """Whether a room still admits anyone."""

    OPEN = "open"
    CLOSED = "closed"


class ClosedBy(StrEnum):
    """Who or what closed a room."""

    OWNER = "owner"
    # Комната простояла пустой час (MR-D1).
    IDLE = "idle"
    ADMIN = "admin"
    # Аккаунт владельца уходит: окно удаления закрывает его комнаты.
    ACCOUNT = "account"


class RoomRule(StrEnum):
    """A rule of rooms; the value is the API's error code."""

    TITLE_TOO_LONG = "title_too_long"
    ROOM_CLOSED = "room_closed"


class RoomRuleError(ValueError):
    """A room breaks a rule."""

    def __init__(self, rule: RoomRule) -> None:
        super().__init__(rule.value)
        self.rule = rule
        self.code = rule.value


@dataclass(frozen=True, slots=True)
class Room:
    """What the rules need of a room."""

    id: UUID
    owner_id: UUID
    org_id: UUID | None
    title: str | None
    lk_room_name: str
    state: RoomState
    notes_on: bool
    closed_at: datetime | None = None
    closed_by: ClosedBy | None = None

    @property
    def is_open(self) -> bool:
        """Whether the room admits anyone."""
        return self.state is RoomState.OPEN


def checked_title(raw: str | None) -> str | None:
    """The trimmed title, or None for an untitled room; longer than 200 is refused."""
    if raw is None:
        return None
    title = raw.strip()
    if not title:
        return None
    if len(title) > TITLE_MAX:
        raise RoomRuleError(RoomRule.TITLE_TOO_LONG)
    return title


def new_livekit_name() -> str:
    """A fresh LiveKit room name: `r-` and 16 hex digits, unique by the table's index."""
    return f"r-{secrets.token_hex(LIVEKIT_NAME_BYTES)}"


def is_livekit_name(value: str) -> bool:
    """Whether a string has the shape of a room's LiveKit name, new or carried over."""
    return LIVEKIT_NAME.fullmatch(value) is not None


def closed(room: Room, by: ClosedBy, at: datetime) -> Room:
    """The room closed by `by` at `at`; closing a closed room keeps its first close."""
    if not room.is_open:
        return room
    return replace(room, state=RoomState.CLOSED, closed_at=at, closed_by=by)


def changed(room: Room, *, title: str | None = None, notes_on: bool | None = None) -> Room:
    """The room with a new title or notes switch; a closed room is not changed."""
    if not room.is_open:
        raise RoomRuleError(RoomRule.ROOM_CLOSED)
    return replace(
        room,
        title=room.title if title is None else checked_title(title),
        notes_on=room.notes_on if notes_on is None else notes_on,
    )


def room_ceiling(plan_value: int | None, platform_ceiling: int = PLATFORM_CEILING) -> int:
    """How many may be in a call: the plan's value capped by the platform's, at least two.

    A plan without a value takes the platform's ceiling (MR-D2, agent-derived).
    """
    platform = max(CEILING_MIN, platform_ceiling)
    if plan_value is None:
        return platform
    return max(CEILING_MIN, min(plan_value, platform))
