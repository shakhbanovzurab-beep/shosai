"""A task's three time fields as a read shows them (tasks plan §3.9).

They are columns of the task's row — the stopwatch's sum of its spans, kept with them, the
timer, plan and fact — so a board, a list and a panel read them with the task and no read
takes a statement or a subquery more. A field is null while unused, as the cabinet's mocks
answer.
"""

from shosai.features.tasks.application.task_parts import ClockFacts
from shosai.features.tasks.domain.clocks import (
    Stopwatch,
    TaskClocks,
    Timer,
    tracking_of,
)


def clocks_of(record: ClockFacts) -> TaskClocks:
    """The time fields of a task's row."""
    total = record.stopwatch_total_ms
    stopwatch = (
        None
        if total is None
        else Stopwatch(
            record.stopwatch_since,
            total,
            record.stopwatch_by_column or {},
        )
    )
    length = record.timer_length_ms
    timer = (
        None if length is None else Timer(length, record.timer_ends_at, record.timer_paused_left_ms)
    )
    return TaskClocks(stopwatch, timer, tracking_of(record.plan_minutes, record.fact_minutes))
