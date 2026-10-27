"""Leo's voice conversation as the WS gateway carries it (ADR 0070, LV-D2, LV-D7).

The cabinet's `hello` names the space — Personal or a workspace — the thread to go on with,
the page and the interface's language. The server's control frames tell the conversation's
state, both sides' words as they are heard so far, the steps of Leo's tools, the cards they
prepared, the cards approved by voice and why the conversation ended; speech goes both ways
in binary frames, PCM16 mono at the rates `ready` names. A conversation lasts at most 30
minutes and ends after two in which nobody spoke; a person has one at a time.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Any, Final
from uuid import UUID

PROTOCOL: Final = 1
# Голос, который выбрал владелец (ADR 0070): Charon — встроенный голос Gemini Live.
VOICE: Final = "Charon"
# Пауза, после которой Gemini считает реплику человека законченной.
SILENCE_MS: Final = 500
# Gemini Live говорит PCM16 24 кГц; кабинет проигрывает по частоте из `ready`.
OUTPUT_RATE: Final = 24_000
LONGEST: Final = timedelta(minutes=30)
IDLE: Final = timedelta(minutes=2)
PATH_MAX: Final = 512
LOCALE_MAX: Final = 35

type Frame = dict[str, Any]


class VoiceState(StrEnum):
    """What the conversation is doing, for the orb."""

    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class VoiceEnd(StrEnum):
    """Why a conversation ended, as the `ended` frame names it."""

    # Человек закончил разговор или закрыл кабинет.
    ENDED = "ended"
    IDLE = "idle"
    TIME_LIMIT = "time_limit"
    MINUTES = "minutes_exhausted"
    SHUTDOWN = "server_shutdown"
    # Сессия Gemini оборвалась или не отвечает.
    PROVIDER = "voice_unavailable"


class MalformedHelloError(ValueError):
    """A field of `hello` is not what the protocol says."""


@dataclass(frozen=True, slots=True)
class VoicePlace:
    """Where the conversation happens: the workspace or Personal, the thread, the page, the
    interface's language."""

    workspace_id: UUID | None
    thread_id: UUID | None
    path: str | None
    locale: str | None


def voice_place(fields: Mapping[str, Any]) -> VoicePlace:
    """The place from `hello`'s own fields; `MalformedHelloError` when one is malformed."""
    scope, path, locale = fields.get("scope"), fields.get("path"), fields.get("locale")
    if not isinstance(scope, dict):
        raise MalformedHelloError
    if path is not None and not (isinstance(path, str) and path.startswith("/")):
        raise MalformedHelloError
    if locale is not None and not (isinstance(locale, str) and 0 < len(locale) <= LOCALE_MAX):
        raise MalformedHelloError
    return VoicePlace(
        workspace_of(scope), uuid_of(fields.get("thread_id")), path[:PATH_MAX] if path else None,
        locale,
    )  # fmt: skip


def workspace_of(scope: Mapping[str, Any]) -> UUID | None:
    """The workspace of a scope, None for Personal."""
    kind = scope.get("kind")
    if kind == "personal":
        return None
    workspace = uuid_of(scope.get("workspace_id")) if kind == "workspace" else None
    if workspace is None:
        raise MalformedHelloError
    return workspace


def uuid_of(value: object) -> UUID | None:
    """A UUID from its text, None for a missing one."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise MalformedHelloError
    try:
        return UUID(value)
    except ValueError as wrong:
        raise MalformedHelloError from wrong


def ready(session: UUID, thread: UUID, input_rate: int) -> Frame:
    """The conversation is open: its id, its thread and the audio rates both ways."""
    return {
        "type": "ready", "session": str(session), "thread_id": str(thread),
        "input_rate": input_rate, "output_rate": OUTPUT_RATE,
    }  # fmt: skip


def state(current: VoiceState) -> Frame:
    """What the conversation does now."""
    return {"type": "state", "state": current.value}


def transcript(who: str, text: str, *, final: bool) -> Frame:
    """One side's words of the exchange so far; `final` when the side finished."""
    return {"type": "transcript", "who": who, "text": text, "final": final}


def step(activity: str, status: str) -> Frame:
    """A step of one of Leo's tools."""
    return {"type": "step", "activity": activity, "status": status}


def proposed(action_id: UUID) -> Frame:
    """A write became a card for the person to decide on the screen."""
    return {"type": "action.proposed", "action_id": str(action_id)}


def decided(action_id: UUID) -> Frame:
    """A card was approved by voice; the cabinet re-reads it and the data it changed."""
    return {"type": "action.decided", "action_id": str(action_id)}


def ended(end: VoiceEnd) -> Frame:
    """Why the conversation ended."""
    return {"type": "ended", "code": end.value}


INTERRUPTED: Final[Frame] = {"type": "interrupted"}
