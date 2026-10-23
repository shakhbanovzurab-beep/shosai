"""Tasks' views as the contract's shapes, and the contract's bodies as a change of a task."""

from datetime import UTC, date, datetime
from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import Header
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.idempotency.http import CLIENT_KEY_MAX_LENGTH, IDEMPOTENCY_KEY_HEADER
from shosai.core.kernel.errors import AppError
from shosai.features.tasks.application.task_edits import Edit
from shosai.features.tasks.application.task_parts import AttachmentView
from shosai.features.tasks.application.views import CardView, TaskView
from shosai.features.tasks.channels.http.card_models import AssigneeOut, Card, CoverOut, SpaceOut
from shosai.features.tasks.channels.http.detail_models import (
    AttachmentOut,
    DayRule,
    MonthRule,
    PersonOut,
    PlacementOut,
    Recurrence,
    SourceFindingOut,
    SourceMeetingOut,
    SourceOut,
    SubtaskOut,
    TaskDetail,
    TaskItem,
    WeekRule,
)
from shosai.features.tasks.domain.changes import UNSET, TaskChange, Unset
from shosai.features.tasks.domain.recurrence import Every
from shosai.features.tasks.domain.recurrence import Recurrence as Schedule
from shosai.features.tasks.domain.tasks import Assignee, Priority, TaskStatus

OptionalIdempotencyKey = Annotated[
    str | None,
    Header(
        alias=IDEMPOTENCY_KEY_HEADER,
        min_length=1,
        max_length=CLIENT_KEY_MAX_LENGTH,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description="Optional: a key unique to one create, repeated on its retries.",
    ),
]
# Поля, которым null не положен: их можно не прислать, но не очистить.
NOT_NULL: Final = ("title", "description", "status")


class Strict(BaseModel):
    """A request body: unknown fields are refused."""

    model_config = ConfigDict(extra="forbid")


class TaskCreateBody(Strict):
    """A task made by hand, in the person's space or in a workspace."""

    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: Priority | None = None
    starts_on: date | None = None
    due_on: date | None = None
    recurrence: Recurrence | None = None
    workspace_id: UUID | None = None
    assignee_id: UUID | None = None
    assignee_name: str | None = None
    project_id: UUID | None = None


class TaskPatchBody(Strict):
    """A change of a task by field presence: a field left out stays, `null` clears it."""

    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    starts_on: date | None = None
    due_on: date | None = None
    assignee_id: UUID | None = None
    assignee_name: str | None = None
    recurrence: Recurrence | None = None
    cover_attachment_id: UUID | None = None
    project_id: UUID | None = None


class TasksDeleteBody(Strict):
    """Tasks to delete after the cabinet's Undo, all or none."""

    task_ids: list[UUID] = Field(min_length=1, max_length=500)


def invalid() -> AppError:
    """A body the contract refuses."""
    return AppError("validation_error", HTTPStatus.UNPROCESSABLE_CONTENT)


def schedule_of(rule: Recurrence | None) -> Schedule | None:
    """The domain's schedule of the contract's."""
    if rule is None:
        return None
    if isinstance(rule, WeekRule):
        return Schedule(Every.WEEK, tuple(rule.weekdays))
    if isinstance(rule, MonthRule):
        return Schedule(Every.MONTH, day=rule.day)
    return Schedule(Every.DAY)


def rule_of(schedule: Schedule | None) -> Recurrence | None:
    """The contract's schedule of the domain's."""
    if schedule is None:
        return None
    if schedule.every is Every.WEEK:
        return WeekRule(every="week", weekdays=list(schedule.weekdays))
    if schedule.every is Every.MONTH:
        return MonthRule(every="month", day=schedule.day or 1)
    return DayRule(every="day")


def edit_of(body: TaskPatchBody) -> Edit:
    """The change a body asks for, by the fields it sends."""
    sent = body.model_fields_set
    if any(name in sent and getattr(body, name) is None for name in NOT_NULL):
        raise invalid()
    if {"assignee_id", "assignee_name"} <= sent:
        raise invalid()
    return Edit(
        change=_change_of(body, sent),
        cover=body.cover_attachment_id if "cover_attachment_id" in sent else UNSET,
        sent_assignee_id="assignee_id" in sent,
        sent_assignee_name="assignee_name" in sent,
    )


def _kept[T](value: T | None) -> T | Unset:
    """A field that cannot be cleared: left out when it is not sent."""
    return UNSET if value is None else value


def _assignee_of(body: TaskPatchBody, sent: set[str]) -> Assignee | Unset:
    if "assignee_id" in sent:
        return Assignee(user_id=body.assignee_id)
    if "assignee_name" in sent:
        return Assignee(name=body.assignee_name)
    return UNSET


def _change_of(body: TaskPatchBody, sent: set[str]) -> TaskChange:
    return TaskChange(
        title=_kept(body.title),
        description=_kept(body.description),
        status=_kept(body.status),
        priority=body.priority if "priority" in sent else UNSET,
        starts_on=body.starts_on if "starts_on" in sent else UNSET,
        due_on=body.due_on if "due_on" in sent else UNSET,
        recurrence=schedule_of(body.recurrence) if "recurrence" in sent else UNSET,
        assignee=_assignee_of(body, sent),
        project_id=body.project_id if "project_id" in sent else UNSET,
    )


def _card(card: CardView) -> dict[str, object]:
    who = card.assignee
    space = card.space
    return {
        "id": card.id,
        "title": card.title,
        "status": card.status,
        "priority": card.priority,
        "starts_on": card.starts_on,
        "due_on": card.due_on,
        "assignee": None if who is None else AssigneeOut(user_id=who.user_id, name=who.name),
        "recurring": card.recurring,
        "leo_fields": list(card.leo_fields),
        "space": None
        if space is None
        else SpaceOut(
            workspace_id=space.org_id, workspace_slug=space.slug, workspace_name=space.name
        ),
        "can_delete": card.can_delete,
        "subtasks_done": card.counts.subtasks_done,
        "subtasks_total": card.counts.subtasks_total,
        "comment_count": card.counts.comments,
        "attachment_count": card.counts.attachments,
        "cover": None
        if card.cover is None
        else CoverOut(attachment_id=card.cover.attachment_id, preview_url=card.cover.preview_url),
    }


def card_out(view: TaskView) -> Card:
    """The card of a task."""
    return Card.model_validate(_card(view.card))


def item_out(view: TaskView) -> TaskItem:
    """A list's item of a task."""
    return TaskItem.model_validate(
        {
            **_card(view.card),
            "project_id": view.project_id,
            "meeting_id": view.meeting_id,
            "created_at": view.created_at,
            "updated_at": view.updated_at,
            "completed_at": view.completed_at,
        }
    )


def detail_out(view: TaskView) -> TaskDetail:
    """A task as its panel shows it."""
    meeting = view.meeting
    finding = view.finding
    source = SourceOut(
        kind=view.source,
        meeting=None
        if meeting is None
        else SourceMeetingOut(id=meeting.id, title=meeting.title, started_at=meeting.started_at),
        finding=None
        if finding is None
        else SourceFindingOut(quote=finding.quote, start_ms=finding.start_ms),
    )
    placement = view.placement
    return TaskDetail.model_validate(
        {
            **_card(view.card),
            "description": view.description,
            "recurrence": rule_of(view.recurrence),
            "source": source,
            "subtasks": [
                SubtaskOut(id=line.id, title=line.title, done=line.done) for line in view.subtasks
            ],
            "attachments": [attachment_out(attachment) for attachment in view.attachments],
            "placement": None
            if placement is None
            else PlacementOut(board_id=placement[0], column_id=placement[1]),
            "created_at": view.created_at,
            "updated_at": view.updated_at,
            "completed_at": view.completed_at,
            "server_now": datetime.now(UTC),
        }
    )


def attachment_out(view: AttachmentView) -> AttachmentOut:
    """A file of a task as the panel lists it."""
    who = view.added_by
    return AttachmentOut(
        id=view.id, name=view.name, content_type=view.content_type, size_bytes=view.size_bytes,
        image=view.image, preview_url=view.preview_url,
        added_by=PersonOut(user_id=who.user_id, name=who.name), added_at=view.added_at,
    )  # fmt: skip
