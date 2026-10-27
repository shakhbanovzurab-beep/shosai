"""Joining a room by its link: who gets in, with which rights and for how long (MR-D2).

The link admits directly, with no waiting room. A refusal is decided in one order: a token
nobody holds and a room whose owner is hidden answer the same `not_found`, so the link
reveals nothing, as notes' share links do. Then a closed room says the meeting has ended, a
principal the owner removed is refused, and a full room is refused last. Everyone in a call has
the same rights in the SFU — the owner's extra powers (end, remove, record, notes) are
meetings' routes, never LiveKit's `room_admin`, so a modified client cannot use them.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final

from shosai.features.meetings.domain.principals import Principal
from shosai.features.meetings.domain.rooms import Room

# Пропуск LiveKit живёт 10 минут: подключённому клиенту SFU продлевает его сам, а
# неиспользованный не воскрешает закрытую комнату (урок черновика: токены на час).
LIVEKIT_TOKEN_TTL: Final = timedelta(minutes=10)
# Пропуск комнаты — для маршрутов meetings (чат, доска); продлевается, пока комната открыта.
ROOM_PASS_TTL: Final = timedelta(hours=12)
# Сколько входов по ссылке в минуту с одного адреса.
JOINS_PER_MINUTE: Final = 10


class CallRole(StrEnum):
    """A principal's part in a call."""

    OWNER = "owner"
    PARTICIPANT = "participant"


class JoinRefusal(StrEnum):
    """Why a link did not admit; the value is the API's error code."""

    NOT_FOUND = "not_found"
    ROOM_FINISHED = "room_finished"
    REMOVED = "removed"
    ROOM_FULL = "room_full"


@dataclass(frozen=True, slots=True)
class Grants:
    """What a session may do in the SFU; subscribing is always allowed."""

    can_publish: bool
    can_publish_data: bool
    # Свои атрибуты: поднятая рука и сведения об устройстве.
    can_update_own_metadata: bool
    # Скрытого участника SFU не показывает остальным (зритель трансляции).
    hidden: bool = False


# Звонок — разговор равных: голос, видео, экран, реакции, доска и рука у каждого.
IN_CALL: Final = Grants(can_publish=True, can_publish_data=True, can_update_own_metadata=True)


@dataclass(frozen=True, slots=True)
class JoinFacts:
    """What the join knows when it decides."""

    # Комнаты с этим токеном нет ни в одном доме.
    room: Room | None
    # Владелец скрыт: аккаунт в окне удаления или заблокирован.
    owner_hidden: bool
    principal: Principal
    banned: bool
    # Сколько участников сейчас в звонке, не считая egress.
    present: int
    ceiling: int


def join_refusal(facts: JoinFacts) -> JoinRefusal | None:
    """Why the link refuses, or None when it admits."""
    if facts.room is None or facts.owner_hidden:
        return JoinRefusal.NOT_FOUND
    if not facts.room.is_open:
        return JoinRefusal.ROOM_FINISHED
    if facts.banned:
        return JoinRefusal.REMOVED
    if facts.present >= facts.ceiling:
        return JoinRefusal.ROOM_FULL
    return None


def call_role(room: Room, principal: Principal) -> CallRole:
    """The owner of the room is its owner on every device; everyone else participates."""
    return CallRole.OWNER if principal.user_id == room.owner_id else CallRole.PARTICIPANT


def may_remove(room: Room, actor: Principal, target: Principal) -> bool:
    """Only the owner removes, and never themselves."""
    return call_role(room, actor) is CallRole.OWNER and target != actor
