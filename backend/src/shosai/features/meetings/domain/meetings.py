"""A meeting's life: start, end, the 6-hour ceiling and the silence rule (plan §3.4, MT-D2).

A meeting is `active` from its start until it ends — by the client (`completed`, or
`failed` when its recording broke), by the silence sweep 5 minutes after its last audio,
or at 6 hours — and then stays ended: a repeated end changes nothing, so the shipped
clients' retries with a fresh `ended_at` never move it or start a second run. The server
decides when a meeting ended: never before its last line, never after now or its 6 hours
(the draft copied the client's `ended_at`, so a client could erase its minutes).
"""

import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final

MAX_LENGTH: Final = timedelta(hours=6)
WARNING_BEFORE: Final = timedelta(minutes=10)
# Тишина считается от последнего аудиокадра, а не от последней фразы: паузы в речи
# черновик намерил до 92 минут, а запись при этом идёт.
SILENCE_AFTER: Final = timedelta(minutes=5)
TITLE_MAX: Final = 256


class MeetingStatus(StrEnum):
    """Where a meeting stands; an ended one never becomes active again."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class MeetingSource(StrEnum):
    """How the meeting came to Shosai."""

    LIVE = "live"
    IMPORT = "import"


class EndCause(StrEnum):
    """Why a meeting ended."""

    CLIENT = "client"
    # Клиент сообщил, что запись сломалась; встреча всё равно идёт в обработку (inv-7).
    CLIENT_FAILED = "client_failed"
    SILENCE = "silence"
    CEILING = "ceiling"
    # Тот же человек начал новую встречу на том же устройстве.
    REPLACED = "replaced"
    # Импорт заканчивается длиной своей записи.
    RECORDING = "recording"


class TitleRuleError(ValueError):
    """A title is empty after trimming (the native rename's 422 `title_empty`)."""

    code = "title_empty"

    def __init__(self) -> None:
        super().__init__(self.code)


def checked_title(raw: str) -> str:
    """The trimmed title without control characters, cut to 256 characters as the draft did."""
    title = "".join(char for char in raw if unicodedata.category(char) != "Cc").strip()
    if not title:
        raise TitleRuleError
    return title[:TITLE_MAX]


def title_or_default(raw: str, started_at: datetime) -> str:
    """The title, or the meeting's start in UTC when the client sent none: no words to translate."""
    try:
        return checked_title(raw)
    except TitleRuleError:
        return started_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def ends_by(started_at: datetime) -> datetime:
    """When a meeting started at `started_at` ends at the latest."""
    return started_at + MAX_LENGTH


def warn_at(started_at: datetime) -> datetime:
    """When the person is warned that the meeting is about to reach its ceiling."""
    return ends_by(started_at) - WARNING_BEFORE


@dataclass(frozen=True, slots=True)
class MeetingClock:
    """What decides a meeting's end: its start, its state and the end of its last line."""

    started_at: datetime
    status: MeetingStatus = MeetingStatus.ACTIVE
    ended_at: datetime | None = None
    last_line_end: datetime | None = None

    def __post_init__(self) -> None:
        if (self.status is MeetingStatus.ACTIVE) != (self.ended_at is None):
            message = "у идущей встречи нет конца, у закончившейся он есть"
            raise ValueError(message)
        if self.ended_at is not None and self.ended_at < self.started_at:
            message = "встреча не кончается раньше, чем началась"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class Ending:
    """The outcome of ending a meeting; `changed` is false for a repeat."""

    status: MeetingStatus
    ended_at: datetime
    changed: bool


def clamped_end(clock: MeetingClock, asked: datetime, now: datetime) -> datetime:
    """`asked` held between the meeting's last line and the earlier of now and its 6 hours."""
    upper = max(clock.started_at, min(now, ends_by(clock.started_at)))
    floor = min(max(clock.started_at, clock.last_line_end or clock.started_at), upper)
    return min(max(asked, floor), upper)


def end_meeting(
    clock: MeetingClock, *, cause: EndCause, now: datetime, asked: datetime | None = None
) -> Ending:
    """End an active meeting at the server's time; an ended one stays as it is."""
    if clock.status is not MeetingStatus.ACTIVE and clock.ended_at is not None:
        return Ending(clock.status, clock.ended_at, changed=False)
    status = MeetingStatus.FAILED if cause is EndCause.CLIENT_FAILED else MeetingStatus.COMPLETED
    return Ending(status, clamped_end(clock, asked or now, now), changed=True)


def last_sign_of_life(
    started_at: datetime, last_audio: datetime | None, last_line_end: datetime | None
) -> datetime:
    """The latest of the meeting's start, its last audio frame and the end of its last line."""
    return max(moment for moment in (started_at, last_audio, last_line_end) if moment is not None)


def sweep_cause(clock: MeetingClock, last_audio: datetime | None, now: datetime) -> EndCause | None:
    """Why the sweep ends an active meeting now, if it does: its ceiling first, then silence."""
    if clock.status is not MeetingStatus.ACTIVE:
        return None
    if now >= ends_by(clock.started_at):
        return EndCause.CEILING
    last = last_sign_of_life(clock.started_at, last_audio, clock.last_line_end)
    if now - last >= SILENCE_AFTER:
        return EndCause.SILENCE
    return None


def sweep_end(clock: MeetingClock, last_audio: datetime | None, now: datetime) -> Ending | None:
    """The sweep's end of an active meeting: at its last sign of life, at most its 6 hours."""
    cause = sweep_cause(clock, last_audio, now)
    if cause is None:
        return None
    last = last_sign_of_life(clock.started_at, last_audio, clock.last_line_end)
    return end_meeting(clock, cause=cause, now=now, asked=last)


def needs_run(*, kept: bool, has_speech: bool) -> bool:
    """Whether an ended meeting goes to processing: it is kept and something was said."""
    return kept and has_speech
