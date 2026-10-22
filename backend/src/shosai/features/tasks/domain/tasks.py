"""A task as the one store keeps it (tasks plan §3.4, TK-D11, TK-D12).

Its status is the truth every view follows: a board's column, Today, a workspace's list, a
meeting's page, Jira. Priority may be empty (KG-D6). A due day is a calendar day that keeps
its day in every zone (ADR 0058). A personal task names who does it as written; a workspace
task names a member, or, when no member matched, keeps the name as written (TK-D3). Each
broken rule carries the API's error code, the one the cabinet words.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

TITLE_MAX: Final = 200
DESCRIPTION_MAX: Final = 10_000
ASSIGNEE_NAME_MAX: Final = 80


class TaskStatus(StrEnum):
    """Where a task stands; a board's column of the same kind shows it."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Priority(StrEnum):
    """How urgent a task is, the most urgent first; a task may have none."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskSource(StrEnum):
    """Where a task came from."""

    MANUAL = "manual"
    MEETING = "meeting"
    HUB = "hub"
    MAIL = "mail"
    JIRA = "jira"


class CreatedBy(StrEnum):
    """Who wrote the task: the person, Leo on their approval, a meeting's notes, a sync."""

    PERSON = "person"
    LEO = "leo"
    MEETING = "meeting"
    SYNC = "sync"


class LeoField(StrEnum):
    """A field Leo filled from a meeting and the person has not changed since (KG-D10)."""

    ASSIGNEE = "assignee"
    DUE = "due"
    PRIORITY = "priority"


class TaskRule(StrEnum):
    """A rule of tasks; the value is the API's error code."""

    TITLE_REQUIRED = "title_required"
    TITLE_TOO_LONG = "title_too_long"
    DESCRIPTION_TOO_LONG = "description_too_long"
    RANGE_INVALID = "range_invalid"
    RECURRENCE_INVALID = "recurrence_invalid"
    # Имя исполнителя и вид исполнителя по пространству кабинет отдельным текстом не называет.
    INVALID = "validation_error"


class TaskRuleError(ValueError):
    """A task breaks a rule."""

    def __init__(self, rule: TaskRule) -> None:
        super().__init__(rule.value)
        self.rule = rule
        self.code = rule.value


def checked_title(raw: str) -> str:
    """The trimmed title, 1 to 200 characters, or the rule it breaks."""
    title = raw.strip()
    if not title:
        raise TaskRuleError(TaskRule.TITLE_REQUIRED)
    if len(title) > TITLE_MAX:
        raise TaskRuleError(TaskRule.TITLE_TOO_LONG)
    return title


def checked_description(raw: str) -> str:
    """The description as written, Markdown up to 10 000 characters."""
    if len(raw) > DESCRIPTION_MAX:
        raise TaskRuleError(TaskRule.DESCRIPTION_TOO_LONG)
    return raw


def checked_assignee_name(raw: str | None) -> str | None:
    """A name as written, trimmed to 1 to 80 characters; none clears it."""
    if raw is None:
        return None
    name = raw.strip()
    if not name or len(name) > ASSIGNEE_NAME_MAX:
        raise TaskRuleError(TaskRule.INVALID)
    return name


@dataclass(frozen=True, slots=True)
class Assignee:
    """Who does a task: a member of its workspace, or a name as written, or nobody (the owner)."""

    user_id: UUID | None = None
    name: str | None = None


def checked_assignee(org_id: UUID | None, assignee: Assignee) -> Assignee:
    """The assignee a task of this space may have.

    A member is named only in a workspace; a name stands only where no member is named.
    """
    if assignee.user_id is not None and (org_id is None or assignee.name is not None):
        raise TaskRuleError(TaskRule.INVALID)
    return Assignee(assignee.user_id, checked_assignee_name(assignee.name))


def completed_at_after(
    status: TaskStatus, completed_at: datetime | None, new_status: TaskStatus, now: datetime
) -> datetime | None:
    """When the task was completed after a status change: set exactly while it is done.

    A done task that stays done keeps its moment; a task reopened loses it.
    """
    if new_status is not TaskStatus.DONE:
        return None
    if status is TaskStatus.DONE and completed_at is not None:
        return completed_at
    return now


def in_today(
    status: TaskStatus,
    due_on: date | None,
    completed_at: datetime | None,
    day: date,
    zone: ZoneInfo,
) -> bool:
    """Whether a personal task belongs to the person's Today (TK-D11).

    Open tasks due on or before the day stay until done or moved — they never vanish at
    midnight; done ones show on the day they were completed, in the person's zone.
    """
    if status is TaskStatus.DONE:
        return completed_at is not None and completed_at.astimezone(zone).date() == day
    return due_on is not None and due_on <= day
