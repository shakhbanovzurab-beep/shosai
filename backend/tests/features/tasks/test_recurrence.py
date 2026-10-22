"""A recurring task's schedule answers as the cabinet's `domain/recurrence.test.ts` does."""

import calendar
from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.tasks.domain.changes import UNSET, Schedule, TaskChange, schedule_after
from shosai.features.tasks.domain.recurrence import (
    WEEK,
    Every,
    Recurrence,
    Weekday,
    checked_recurrence,
    first_due,
    next_due,
    occurrence_from,
    recurrence_json,
    recurrence_of,
    shifted_start,
)
from shosai.features.tasks.domain.tasks import TaskRule, TaskRuleError

DAYS = st.dates(min_value=date(2027, 1, 1), max_value=date(2028, 12, 31))
WEEKDAY_SETS = st.sets(st.sampled_from(WEEK), min_size=1).map(lambda days: tuple(sorted(days)))
DAILY = Recurrence(Every.DAY)
FRIDAYS = Recurrence(Every.WEEK, (Weekday.FRI,))


@given(DAYS)
def test_a_daily_task_comes_the_day_after_its_due_day_when_that_day_has_not_passed(
    due: date,
) -> None:
    assert next_due(DAILY, due, due) == due + timedelta(days=1)


def test_past_dates_are_skipped_and_never_counted_from_the_completion_day() -> None:
    assert next_due(DAILY, date(2026, 10, 19), date(2026, 10, 21)) == date(2026, 10, 21)
    # Закрыта рано: следующая пятница после исходного срока, а не после закрытия.
    assert next_due(FRIDAYS, date(2026, 10, 23), date(2026, 10, 20)) == date(2026, 10, 30)
    assert next_due(FRIDAYS, date(2026, 10, 9), date(2026, 10, 21)) == date(2026, 10, 23)


@given(WEEKDAY_SETS, DAYS)
def test_a_week_lands_on_the_first_chosen_day_within_seven_days(
    weekdays: tuple[Weekday, ...], start: date
) -> None:
    found = occurrence_from(Recurrence(Every.WEEK, weekdays), start)

    assert start <= found <= start + timedelta(days=6)
    assert WEEK[found.weekday()] in weekdays
    skipped = (start + timedelta(days=n) for n in range((found - start).days))
    assert all(WEEK[day.weekday()] not in weekdays for day in skipped)


@given(st.integers(min_value=1, max_value=31), DAYS)
def test_a_month_day_past_a_shorter_month_falls_on_its_last_day(day: int, start: date) -> None:
    found = occurrence_from(Recurrence(Every.MONTH, day=day), start)

    assert found >= start
    assert found.day == min(day, calendar.monthrange(found.year, found.month)[1])


def test_the_month_s_last_day_and_the_year_s_turn() -> None:
    monthly = Recurrence(Every.MONTH, day=31)

    assert next_due(monthly, date(2027, 1, 31), date(2027, 1, 31)) == date(2027, 2, 28)
    assert next_due(monthly, date(2028, 1, 31), date(2028, 1, 31)) == date(2028, 2, 29)
    first = Recurrence(Every.MONTH, day=1)
    assert next_due(first, date(2027, 12, 1), date(2027, 12, 5)) == date(2028, 1, 1)


def test_a_task_without_a_due_day_gets_the_first_date_from_today() -> None:
    today = date(2026, 10, 21)
    monday = Recurrence(Every.WEEK, (Weekday.MON,))

    assert first_due(DAILY, today) == today
    assert first_due(monday, today) == date(2026, 10, 26)
    after = schedule_after(Schedule(None, None, None), TaskChange(recurrence=monday), today)
    assert after == Schedule(None, date(2026, 10, 26), monday)


def test_a_range_keeps_its_length() -> None:
    assert shifted_start(date(2026, 10, 20), date(2026, 10, 23), date(2026, 10, 30)) == date(
        2026, 10, 27
    )
    assert shifted_start(None, date(2026, 10, 23), date(2026, 10, 30)) is None


@pytest.mark.parametrize(
    "rule",
    [
        Recurrence(Every.WEEK),
        Recurrence(Every.WEEK, (Weekday.MON, Weekday.MON)),
        Recurrence(Every.MONTH, day=0),
        Recurrence(Every.MONTH, day=32),
        Recurrence(Every.MONTH),
        Recurrence(Every.DAY, day=3),
    ],
)
def test_a_schedule_that_makes_no_sense_is_refused(rule: Recurrence) -> None:
    with pytest.raises(TaskRuleError) as refused:
        checked_recurrence(rule)

    assert refused.value.rule is TaskRule.RECURRENCE_INVALID


@pytest.mark.parametrize(
    "rule", [DAILY, FRIDAYS, Recurrence(Every.MONTH, day=31), Recurrence(Every.WEEK, WEEK)]
)
def test_a_schedule_reads_back_as_it_was_kept(rule: Recurrence) -> None:
    assert checked_recurrence(rule) == rule
    assert recurrence_of(recurrence_json(rule)) == rule


def test_a_start_goes_with_its_due_day_and_never_after_it() -> None:
    today = date(2026, 10, 21)
    ranged = Schedule(date(2026, 10, 20), date(2026, 10, 23), None)

    cleared = schedule_after(ranged, TaskChange(due_on=None), today)

    assert cleared == Schedule(None, None, None)
    with pytest.raises(TaskRuleError):
        schedule_after(ranged, TaskChange(starts_on=date(2026, 10, 24)), today)
    assert schedule_after(ranged, TaskChange(title="Новое", due_on=UNSET), today) == ranged
