"""A task's fields, its change by field presence and Today (tasks plan §3.4, TK-D11)."""

import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from shosai.features.tasks.domain.changes import UNSET, TaskChange, checked_change
from shosai.features.tasks.domain.tasks import (
    DESCRIPTION_MAX,
    TITLE_MAX,
    Assignee,
    TaskRuleError,
    TaskStatus,
    checked_assignee,
    checked_assignee_name,
    checked_description,
    checked_title,
    completed_at_after,
    in_today,
)

NOW = datetime(2026, 10, 22, 9, tzinfo=UTC)
MOSCOW = ZoneInfo("Europe/Moscow")


def code_of(error: pytest.ExceptionInfo[TaskRuleError]) -> str:
    return error.value.code


@pytest.mark.parametrize(
    ("raw", "code"),
    [(" \t ", "title_required"), ("я" * (TITLE_MAX + 1), "title_too_long")],
)
def test_a_title_is_trimmed_and_bounded(raw: str, code: str) -> None:
    assert checked_title("  Отправить  договор ") == "Отправить  договор"
    assert checked_title("会議の議事録を送る") == "会議の議事録を送る"
    with pytest.raises(TaskRuleError) as error:
        checked_title(raw)
    assert code_of(error) == code


def test_a_description_is_kept_as_written_up_to_its_bound() -> None:
    assert checked_description("  # План\n- пункт\n") == "  # План\n- пункт\n"
    with pytest.raises(TaskRuleError) as error:
        checked_description("x" * (DESCRIPTION_MAX + 1))
    assert code_of(error) == "description_too_long"


def test_a_name_as_written_is_trimmed_and_bounded() -> None:
    assert checked_assignee_name(None) is None
    assert checked_assignee_name(" Анна ") == "Анна"
    for raw in ("  ", "x" * 81):
        with pytest.raises(TaskRuleError) as error:
            checked_assignee_name(raw)
        assert code_of(error) == "validation_error"


def test_a_member_does_only_a_workspace_task_and_a_name_stands_only_without_one() -> None:
    org, member = uuid.uuid4(), uuid.uuid4()

    assert checked_assignee(org, Assignee(user_id=member)) == Assignee(user_id=member)
    assert checked_assignee(org, Assignee(name=" Анна ")) == Assignee(name="Анна")
    assert checked_assignee(None, Assignee(name="Анна")) == Assignee(name="Анна")
    assert checked_assignee(None, Assignee()) == Assignee()
    for space, assignee in ((None, Assignee(user_id=member)), (org, Assignee(member, "Анна"))):
        with pytest.raises(TaskRuleError):
            checked_assignee(space, assignee)


def test_completed_at_is_set_exactly_while_done() -> None:
    earlier = datetime(2026, 10, 1, tzinfo=UTC)

    assert completed_at_after(TaskStatus.TODO, None, TaskStatus.DONE, NOW) == NOW
    assert completed_at_after(TaskStatus.DONE, earlier, TaskStatus.DONE, NOW) == earlier
    assert completed_at_after(TaskStatus.DONE, earlier, TaskStatus.TODO, NOW) is None
    assert completed_at_after(TaskStatus.TODO, None, TaskStatus.IN_PROGRESS, NOW) is None


def test_today_keeps_overdue_tasks_and_those_completed_on_the_day_in_the_persons_zone() -> None:
    day = date(2026, 10, 22)

    assert in_today(TaskStatus.TODO, day, None, day, MOSCOW)
    assert in_today(TaskStatus.IN_PROGRESS, date(2026, 10, 1), None, day, MOSCOW)
    assert not in_today(TaskStatus.TODO, date(2026, 10, 23), None, day, MOSCOW)
    assert not in_today(TaskStatus.TODO, None, None, day, MOSCOW)
    # 21:30 UTC 21 октября — уже 22 октября в Москве.
    late = datetime(2026, 10, 21, 21, 30, tzinfo=UTC)
    assert in_today(TaskStatus.DONE, date(2026, 9, 1), late, day, MOSCOW)
    assert not in_today(TaskStatus.DONE, day, late, day, ZoneInfo("UTC"))


def test_a_change_names_only_the_fields_it_sets_and_null_clears() -> None:
    change = TaskChange(due_on=None, title=" Новое ")

    assert change.present() == {"due_on", "title"}
    assert change.priority is UNSET
    checked = checked_change(change, None)
    assert (checked.title, checked.due_on) == ("Новое", None)
    assert TaskChange().present() == frozenset()


def test_a_change_is_checked_for_the_tasks_space() -> None:
    with pytest.raises(TaskRuleError):
        checked_change(TaskChange(assignee=Assignee(user_id=uuid.uuid4())), None)
    with pytest.raises(TaskRuleError):
        checked_change(TaskChange(description="x" * (DESCRIPTION_MAX + 1)), None)
