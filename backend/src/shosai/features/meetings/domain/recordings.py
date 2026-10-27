"""A video recording of a call (MR-D4, meetings plan §3.5).

The owner records on a paid plan, within their storage. The row is committed `starting`
before the egress starts, so an early webhook always finds it, and one active recording per
room is a unique index. Reports from LiveKit's webhooks and the sweep's reconciliation only
move a recording forward: an earlier state reported late is ignored, and an end state is
never left. A recording that LiveKit stopped at its own limit still wrote a whole file, so it
completes. The file becomes a File Manager file in Recordings; it does not feed notes.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

# Сколько одновременных записей держит платформа и сколько длится одна (стейджинг: 1 и 30 мин).
PLATFORM_CONCURRENT: Final = 1
LENGTH_LIMIT: Final = timedelta(minutes=30)


class RecordingState(StrEnum):
    """Where a recording stands, in the order it moves."""

    STARTING = "starting"
    ACTIVE = "active"
    ENDING = "ending"
    COMPLETE = "complete"
    FAILED = "failed"


ACTIVE_STATES: Final = frozenset(
    {RecordingState.STARTING, RecordingState.ACTIVE, RecordingState.ENDING}
)
_RANK: Final = {
    RecordingState.STARTING: 0,
    RecordingState.ACTIVE: 1,
    RecordingState.ENDING: 2,
    RecordingState.COMPLETE: 3,
    RecordingState.FAILED: 3,
}


class RecordingFailure(StrEnum):
    """Why a recording failed; kept on the row and counted by the metric."""

    START_REFUSED = "start_refused"
    EGRESS_FAILED = "egress_failed"
    EGRESS_ABORTED = "egress_aborted"
    # Sweep не нашёл egress у записи, которая по строкам ещё идёт.
    EGRESS_LOST = "egress_lost"
    # Файл не принят в хранилище владельца.
    NOT_ADOPTED = "not_adopted"


class RecordingRefusal(StrEnum):
    """Why a start is refused, in the order the checks run; the value is the API's code."""

    NOT_FOUND = "room_not_found"
    ROOM_CLOSED = "room_closed"
    NO_LIVE_CALL = "no_live_call"
    NOT_IN_PLAN = "recording_not_in_plan"
    STORAGE_LIMIT = "storage_limit"
    ALREADY_RECORDING = "recording_active"
    PLATFORM_BUSY = "recordings_busy"


@dataclass(frozen=True, slots=True)
class StartFacts:
    """What a start knows when it decides."""

    is_owner: bool
    room_open: bool
    call_live: bool
    in_plan: bool
    storage_left_bytes: int
    room_recording: bool
    platform_active: int
    platform_concurrent: int = PLATFORM_CONCURRENT


def start_refusal(facts: StartFacts) -> RecordingRefusal | None:
    """The first check a start fails, or None when it may start."""
    checks = (
        (not facts.is_owner, RecordingRefusal.NOT_FOUND),
        (not facts.room_open, RecordingRefusal.ROOM_CLOSED),
        (not facts.call_live, RecordingRefusal.NO_LIVE_CALL),
        (not facts.in_plan, RecordingRefusal.NOT_IN_PLAN),
        (facts.storage_left_bytes <= 0, RecordingRefusal.STORAGE_LIMIT),
        (facts.room_recording, RecordingRefusal.ALREADY_RECORDING),
        (facts.platform_active >= facts.platform_concurrent, RecordingRefusal.PLATFORM_BUSY),
    )
    return next((refusal for failed, refusal in checks if failed), None)


def advanced(current: RecordingState, reported: RecordingState) -> RecordingState:
    """The state after a report: forward only, and an end state is final."""
    if _RANK[current] == _RANK[RecordingState.COMPLETE]:
        return current
    return reported if _RANK[reported] > _RANK[current] else current


def over_length(started_at: datetime, now: datetime, limit: timedelta = LENGTH_LIMIT) -> bool:
    """Whether a recording reached its length limit and must be stopped."""
    return now - started_at >= limit
