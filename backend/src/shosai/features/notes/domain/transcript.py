"""Transcript lines: identity, offsets and the live speaker sides (§8.1; plan §3.3).

A line is `(meeting, seq)`: capture gives each live phrase the next `seq` at intake, and a
replay of the same `seq` stores nothing new; two lines with equal text are two lines (the
draft keyed lines by their text's hash and lost a repeated short "yes"). A rebuilt transcript
takes fresh `seq`s above the meeting's highest, so an old `seq` is never reused. A line's
place in the meeting is its offset from the meeting's start; its text holds at most 2 000
characters, and a longer phrase is cut where the caller logs it.
"""

from datetime import datetime
from enum import StrEnum
from typing import Final

LINE_TEXT_MAX: Final = 2000
# Сколько последних строк получает пересоединившийся клиент (`transcript.restore`).
TAIL_MAX: Final = 2000


class Side(StrEnum):
    """Who spoke a live phrase, as the desktop knows it: its microphone or the call."""

    ME = "me"
    THEM = "them"


# Номер говорящего живой строки: владелец — 0, собеседники — 1.
SIDE_SPEAKER: Final = {Side.ME: 0, Side.THEM: 1}


class LineOrigin(StrEnum):
    """Where a stored line came from."""

    LIVE = "live"
    RECORDING = "recording"


def checked_seq(seq: int) -> int:
    """A line's `seq`: a whole number from 1."""
    if seq < 1:
        message = "seq строки — с единицы"
        raise ValueError(message)
    return seq


def offset_ms(meeting_started_at: datetime, at: datetime) -> int:
    """Milliseconds from the meeting's start to `at`, never negative."""
    return max(0, int((at - meeting_started_at).total_seconds() * 1000))


def fitted_text(text: str) -> tuple[str, bool]:
    """The trimmed text within the line cap, and whether it had to be cut."""
    trimmed = text.strip()
    return trimmed[:LINE_TEXT_MAX], len(trimmed) > LINE_TEXT_MAX


def fresh_seqs(highest: int, count: int) -> range:
    """`count` new `seq`s right above the meeting's highest one."""
    if highest < 0 or count < 0:
        message = "seq и количество — неотрицательные"
        raise ValueError(message)
    return range(highest + 1, highest + 1 + count)
