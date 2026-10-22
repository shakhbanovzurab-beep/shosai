"""Tasks and the sets of meetings' tasks in each home (tasks plan §3.4; revision `b3d9e5a7c142`).

`tasks` is the shareable resource `task`: `user_id`, `org_id` and `access` as workspaces'
access policy reads them, its assignee the named reader and its meeting the parent, so a
meeting's task opens to the meeting's readers now and to whoever does it (TK-D2). A task
is done exactly while `completed_at` is set; a member does only a workspace's task and a
name as written stands only where no member does; a meeting's task is keyed by its
finding. `meeting_task_sets` remembers, per meeting, the revision of its notes applied and
whether the person touched any of its tasks (TK-D3).
"""

from datetime import date, datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Table,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.access.shareable import ShareableResource
from shosai.core.db.model_base import ModelBase

STATUSES: Final = "'todo', 'in_progress', 'done'"
PRIORITIES: Final = "'high', 'medium', 'low'"
SOURCES: Final = "'manual', 'meeting', 'hub', 'mail', 'jira'"
CREATORS: Final = "'person', 'leo', 'meeting', 'sync'"
OPEN: Final = "status <> 'done'"


class TaskRecord(ModelBase):
    """A task of a person or a workspace."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("(org_id IS NULL) = (access IS NULL)", name="org_with_access"),
        CheckConstraint(
            "access IS NULL OR access IN ('owner', 'selected', 'organization')",
            name="access_known",
        ),
        CheckConstraint("length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint("length(description) <= 10000", name="description_length"),
        CheckConstraint(f"status IN ({STATUSES})", name="status_known"),
        CheckConstraint(f"priority IS NULL OR priority IN ({PRIORITIES})", name="priority_known"),
        CheckConstraint(
            "(status = 'done') = (completed_at IS NOT NULL)", name="done_when_completed"
        ),
        CheckConstraint(
            "assignee_user_id IS NULL OR org_id IS NOT NULL", name="member_in_workspace"
        ),
        CheckConstraint(
            "assignee_name IS NULL OR (assignee_user_id IS NULL"
            " AND length(assignee_name) BETWEEN 1 AND 80)",
            name="name_without_member",
        ),
        CheckConstraint("project_id IS NULL OR org_id IS NOT NULL", name="project_in_workspace"),
        CheckConstraint(f"source IN ({SOURCES})", name="source_known"),
        CheckConstraint(
            "(source = 'meeting') = (source_meeting_id IS NOT NULL)", name="meeting_source"
        ),
        CheckConstraint(
            "source_finding_id IS NULL OR source_meeting_id IS NOT NULL", name="finding_of_meeting"
        ),
        CheckConstraint(f"created_by IN ({CREATORS})", name="creator_known"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_tasks_user", "user_id"),
        Index("ix_tasks_org", "org_id", postgresql_where=text("org_id IS NOT NULL")),
        Index("ix_tasks_open_user_due", "user_id", "due_on", postgresql_where=text(OPEN)),
        Index(
            "ix_tasks_open_org_due",
            "org_id",
            "due_on",
            postgresql_where=text("status <> 'done' AND org_id IS NOT NULL"),
        ),
        Index(
            "ix_tasks_open_assignee_due",
            "assignee_user_id",
            "due_on",
            postgresql_where=text("status <> 'done' AND assignee_user_id IS NOT NULL"),
        ),
        # Одна задача на пункт встречи; заодно индекс задач встречи.
        Index(
            "uq_tasks_meeting_finding",
            "source_meeting_id",
            "source_finding_id",
            unique=True,
            postgresql_where=text("source_meeting_id IS NOT NULL"),
        ),
        Index("ix_tasks_project", "project_id", postgresql_where=text("project_id IS NOT NULL")),
        Index(
            "ix_tasks_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    access: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(Text, server_default="todo")
    priority: Mapped[str | None] = mapped_column(Text)
    due_on: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignee_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    assignee_name: Mapped[str | None] = mapped_column(Text)
    # Проект пространства — мягкая ссылка на `projects` среза workspaces.
    project_id: Mapped[UUID | None] = mapped_column(Uuid)
    source: Mapped[str] = mapped_column(Text, server_default="manual")
    # Встреча — мягкая ссылка: задача, которую тронули, остаётся и после встречи.
    source_meeting_id: Mapped[UUID | None] = mapped_column(Uuid)
    source_finding_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_by: Mapped[str] = mapped_column(Text, server_default="person")
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MeetingTaskSetRecord(ModelBase):
    """What tasks remember of one meeting's set of tasks (TK-D3)."""

    __tablename__ = "meeting_task_sets"
    __table_args__ = (
        CheckConstraint("revision >= 0", name="revision_not_negative"),
        Index("ix_meeting_task_sets_user", "user_id"),
        Index("ix_meeting_task_sets_org", "org_id", postgresql_where=text("org_id IS NOT NULL")),
    )

    meeting_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    # Ревизия заметок, чьи пункты стали задачами; 0 — перенесённые из черновика.
    revision: Mapped[int] = mapped_column(Integer)
    touched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meeting_gone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Вид ресурса для политики доступа: задача встречи видна читающим встречу и исполнителю.
TASK_RESOURCE: Final = ShareableResource(
    "task",
    cast("Table", TaskRecord.__table__),
    parent=("meeting", "source_meeting_id"),
    reader="assignee_user_id",
)
