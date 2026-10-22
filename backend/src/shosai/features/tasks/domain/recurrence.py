"""A recurring task's schedule (KG-D5, the owner's amendment; tasks plan §3.8).

Every day, every week on chosen days, or every month on a day. When a recurring task is
marked done, the next one is due on the schedule's first date after the original due day,
never before the completer's today — past dates are skipped, never counted from the day it
was done. A range keeps its length, and days 29 to 31 fall on a shorter month's last day.
A task given a schedule without a due day gets the schedule's first date from today.
"""

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Final

from shosai.features.tasks.domain.tasks import TaskRule, TaskRuleError

MONTH_DAYS: Final = 31


class Every(StrEnum):
    """How often a task comes back."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class Weekday(StrEnum):
    """A day of the week, Monday first, as `date.weekday()` counts them."""

    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


WEEK: Final = tuple(Weekday)


@dataclass(frozen=True, slots=True)
class Recurrence:
    """A schedule: every day, every week on its days, or every month on its day."""

    every: Every
    weekdays: tuple[Weekday, ...] = ()
    day: int | None = None


def checked_recurrence(rule: Recurrence) -> Recurrence:
    """The schedule if it makes sense: a week with distinct days, a month with a day 1 to 31."""
    if rule.every is Every.WEEK:
        valid = 0 < len(rule.weekdays) == len(set(rule.weekdays)) and rule.day is None
    elif rule.every is Every.MONTH:
        valid = rule.day is not None and 1 <= rule.day <= MONTH_DAYS and not rule.weekdays
    else:
        valid = not rule.weekdays and rule.day is None
    if not valid:
        raise TaskRuleError(TaskRule.RECURRENCE_INVALID)
    return rule


def occurrence_from(rule: Recurrence, start: date) -> date:
    """The schedule's first date on or after `start`."""
    if rule.every is Every.DAY:
        return start
    if rule.every is Every.WEEK:
        chosen = {WEEK.index(day) for day in rule.weekdays}
        shift = next(step for step in range(7) if (start.weekday() + step) % 7 in chosen)
        return start + timedelta(days=shift)
    day = rule.day or 1
    here = _in_month(start.year, start.month, day)
    if here >= start:
        return here
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return _in_month(year, month, day)


def _in_month(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def first_due(rule: Recurrence, today: date) -> date:
    """The due day a task without one gets when a schedule is set: the first from today."""
    return occurrence_from(rule, today)


def next_due(rule: Recurrence, due_on: date, today: date) -> date:
    """The next task's due day: the first date after the original due day, not before today."""
    return occurrence_from(rule, max(due_on + timedelta(days=1), today))


def shifted_start(starts_on: date | None, due_on: date, next_due_on: date) -> date | None:
    """The next task's start: its range keeps the length it had."""
    return None if starts_on is None else starts_on + (next_due_on - due_on)


def recurrence_json(rule: Recurrence) -> dict[str, object]:
    """The schedule as the API and the database keep it."""
    if rule.every is Every.WEEK:
        return {"every": rule.every.value, "weekdays": [day.value for day in rule.weekdays]}
    if rule.every is Every.MONTH:
        return {"every": rule.every.value, "day": rule.day}
    return {"every": rule.every.value}


def recurrence_of(raw: Mapping[str, object]) -> Recurrence:
    """A stored schedule read back."""
    every = Every(str(raw["every"]))
    days = raw.get("weekdays")
    weekdays = tuple(Weekday(str(day)) for day in days) if isinstance(days, list) else ()
    day = raw.get("day")
    return Recurrence(every, weekdays, day if isinstance(day, int) else None)
