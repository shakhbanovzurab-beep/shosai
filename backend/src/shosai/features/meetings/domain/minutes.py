"""A meeting's minutes: counted once, at most 6 hours (BL-D3, MT-D3).

A live meeting counts from its start until it ends. A desktop recording of the same meeting
raises the count to the recording's length when it is longer, never adds to it; what it
adds is checked against the minutes left before the recording is processed. An import
counts its recording's length. Nothing counts beyond 6 hours.
"""

from datetime import datetime
from typing import Final

from shosai.features.meetings.domain.meetings import MAX_LENGTH

MAX_SECONDS: Final = int(MAX_LENGTH.total_seconds())


def capped(seconds: int) -> int:
    """`seconds` held between zero and the 6-hour ceiling."""
    return min(max(seconds, 0), MAX_SECONDS)


def seconds_between(start: datetime, end: datetime) -> int:
    """Whole seconds from `start` to `end`, within the ceiling."""
    return capped(int((end - start).total_seconds()))


def meeting_seconds(live_seconds: int, recording_seconds: int | None = None) -> int:
    """The meeting's count: the larger of its live length and its recording's, once."""
    return capped(max(live_seconds, recording_seconds or 0))


def added_by_recording(live_seconds: int, recording_seconds: int) -> int:
    """How many seconds a recording adds to its live meeting's count."""
    return meeting_seconds(live_seconds, recording_seconds) - capped(live_seconds)


def recording_fits(duration_seconds: float) -> bool:
    """Whether an imported recording is within the 6-hour ceiling (else `recording_too_long`)."""
    return 0 < duration_seconds <= MAX_SECONDS
