"""Time on a task (tasks plan §3.9, ADR 0061): the stopwatch, the timer, plan and fact.

The stopwatch is the task's own clock (KT-D1): spans, each in the column of the board where
it ran, one running at most. Its total and its time per column count the closed spans; a
running one adds its time on screen, from `running_since` against the server's moment
(KT-D6). The timer counts a length down (KT-D3): running while it has an end, paused while
it has what is left, below zero past the end. A board's automations (KT-D2) act only while
the board shows the stopwatch: a task arriving starts it if the board says so; a move always
closes the span in the old column, then the clock stays stopped when the task is done and
the board stops on done, else it goes on in the new column when it ran or the board restarts
on a move. Times are whole milliseconds, so the totals add up exactly.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from shosai.features.tasks.domain.board_fields import StopwatchAutomations

MINUTE_MS: Final = 60_000
TIMER_MIN_MS: Final = MINUTE_MS
TIMER_MAX_MS: Final = 365 * 24 * 60 * MINUTE_MS
TRACKED_MINUTES_MAX: Final = 6_000_000


def at_ms(moment: datetime) -> datetime:
    """The moment to the whole millisecond, as the clocks keep it."""
    return moment.replace(microsecond=moment.microsecond // 1000 * 1000)


def ms_between(start: datetime, end: datetime) -> int:
    """Whole milliseconds from one moment to another; negative when the end is earlier."""
    return (end - start) // timedelta(milliseconds=1)


@dataclass(frozen=True, slots=True)
class Span:
    """A stretch the stopwatch ran: in a column of a board, or unplaced; open while running."""

    column_id: UUID | None
    started_at: datetime
    stopped_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Stopwatch:
    """The stopwatch: closed time in all and per column, and since when it runs.

    The columns are keyed by their ids as text, as the task's row and the contract key them:
    a board of a thousand running stopwatches reads them without a conversion each.
    """

    running_since: datetime | None
    total_ms: int
    by_column: Mapping[str, int] = field(default_factory=dict)


def stopwatch_of(spans: Sequence[Span]) -> Stopwatch | None:
    """The stopwatch its spans make; none before it first ran or after a reset."""
    if not spans:
        return None
    total, by_column = 0, dict[str, int]()
    running: datetime | None = None
    for span in spans:
        if span.stopped_at is None:
            running = span.started_at
            continue
        took = ms_between(span.started_at, span.stopped_at)
        total += took
        if span.column_id is not None:
            column = str(span.column_id)
            by_column[column] = by_column.get(column, 0) + took
    return Stopwatch(running, total, by_column)


@dataclass(frozen=True, slots=True)
class Timer:
    """The timer: running while it has an end, paused while it has what is left."""

    length_ms: int
    ends_at: datetime | None
    paused_left_ms: int | None


def timer_from(length_ms: int, now: datetime) -> Timer:
    """A timer set anew: the whole length from now."""
    return Timer(length_ms, now + timedelta(milliseconds=length_ms), None)


def held(timer: Timer, *, paused: bool, now: datetime) -> Timer:
    """The timer paused or going on; a repeat changes nothing, the overrun keeps counting."""
    if paused and timer.ends_at is not None:
        return Timer(timer.length_ms, None, ms_between(now, timer.ends_at))
    if not paused and timer.paused_left_ms is not None:
        return Timer(timer.length_ms, now + timedelta(milliseconds=timer.paused_left_ms), None)
    return timer


@dataclass(frozen=True, slots=True)
class TimeTracking:
    """Plan and fact in minutes."""

    plan_minutes: int | None
    fact_minutes: int | None


def tracking_of(plan_minutes: int | None, fact_minutes: int | None) -> TimeTracking | None:
    """Plan and fact, or none while neither is set."""
    if plan_minutes is None and fact_minutes is None:
        return None
    return TimeTracking(plan_minutes, fact_minutes)


@dataclass(frozen=True, slots=True)
class TaskClocks:
    """The three time fields of a task; each none while unused."""

    stopwatch: Stopwatch | None = None
    timer: Timer | None = None
    time_tracking: TimeTracking | None = None


NO_CLOCKS: Final = TaskClocks()

# Автоматизации доски, которая прячет секундомер, — None: ничего не происходит само.
type Automations = StopwatchAutomations | None


def starts_on_arrival(automations: Automations, *, done: bool) -> bool:
    """Whether a task arriving on the board starts its stopwatch."""
    return automations is not None and automations.start_on_arrival and not done


def runs_after_move(automations: Automations, *, was_running: bool, done: bool) -> bool:
    """Whether the stopwatch goes on in the new column once the old one's span is closed."""
    if done and automations is not None and automations.stop_on_done:
        return False
    restarts = automations is not None and automations.restart_on_move and not done
    return was_running or restarts
