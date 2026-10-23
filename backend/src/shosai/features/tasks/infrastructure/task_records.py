"""Tasks and the sets of meetings' tasks in each home (tasks plan §3.4, §3.8).

Revisions `b3d9e5a7c142`, `c8e4a1f6b293`, `a4c6e8b2d397` (the cover), `d9f2b4c6e813` (the
time fields) and `e2b4d6f8a135` (the chat source).

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
    ARRAY,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Table,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.access.shareable import ShareableResource
from shosai.core.db.model_base import ModelBase
from shosai.features.tasks.domain.clocks import TIMER_MAX_MS, TIMER_MIN_MS, TRACKED_MINUTES_MAX

STATUSES: Final = "'todo', 'in_progress', 'done'"
PRIORITIES: Final = "'high', 'medium', 'low'"
SOURCES: Final = "'manual', 'meeting', 'hub', 'mail', 'jira', 'chat'"
MESSENGERS: Final = "'telegram', 'slack'"
# Источник из чата (TK-D13): чат и момент сообщения — ровно у задачи из чата, она — задача
# пространства, сделанная Лео; подключение и ссылка — только у неё.
CHAT_SOURCE: Final = (
    "(source = 'chat') = (source_chat_messenger IS NOT NULL)"
    " AND (source = 'chat') = (source_chat_title IS NOT NULL)"
    " AND (source = 'chat') = (source_chat_message_at IS NOT NULL)"
    " AND (source = 'chat' OR (source_chat_connection_id IS NULL"
    " AND source_chat_message_url IS NULL))"
    " AND (source <> 'chat' OR (org_id IS NOT NULL AND created_by = 'leo'))"
)
CREATORS: Final = "'person', 'leo', 'meeting', 'sync'"
OPEN: Final = "status <> 'done'"
# Снятое расписание — SQL NULL, не JSON null (ревизия `d9f2b4c6e813`).
RECURRENCE_KNOWN: Final = (
    "recurrence IS NULL OR (jsonb_typeof(recurrence) = 'object'"
    " AND recurrence ->> 'every' IN ('day', 'week', 'month'))"
)


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
        CheckConstraint(CHAT_SOURCE, name="chat_source"),
        CheckConstraint(
            f"source_chat_messenger IS NULL OR source_chat_messenger IN ({MESSENGERS})",
            name="chat_messenger_known",
        ),
        CheckConstraint(
            "source_chat_title IS NULL OR length(source_chat_title) BETWEEN 1 AND 255",
            name="chat_title_length",
        ),
        CheckConstraint(
            "source_chat_message_url IS NULL OR length(source_chat_message_url) <= 2048",
            name="chat_link_length",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "starts_on IS NULL OR (due_on IS NOT NULL AND starts_on <= due_on)", name="range"
        ),
        CheckConstraint(RECURRENCE_KNOWN, name="recurrence_known"),
        CheckConstraint(
            "leo_fields <@ ARRAY['assignee', 'due', 'priority']::text[]", name="leo_fields_known"
        ),
        # Сводка секундомера по отрезкам: с какого момента идёт, закрытое время всего и по колонкам.
        CheckConstraint(
            "(stopwatch_total_ms IS NULL) = (stopwatch_by_column IS NULL)"
            " AND (stopwatch_since IS NULL OR stopwatch_total_ms IS NOT NULL)"
            " AND (stopwatch_total_ms IS NULL OR stopwatch_total_ms >= 0)"
            " AND (stopwatch_by_column IS NULL OR jsonb_typeof(stopwatch_by_column) = 'object')",
            name="stopwatch_shape",
        ),
        # Таймер: длина с моментом конца, пока идёт, или с остатком на паузе (ADR 0061).
        CheckConstraint(
            "(timer_length_ms IS NULL AND timer_ends_at IS NULL AND timer_paused_left_ms IS NULL)"
            f" OR (timer_length_ms BETWEEN {TIMER_MIN_MS} AND {TIMER_MAX_MS}"
            " AND num_nonnulls(timer_ends_at, timer_paused_left_ms) = 1)",
            name="timer_shape",
        ),
        CheckConstraint(
            f"plan_minutes IS NULL OR plan_minutes BETWEEN 0 AND {TRACKED_MINUTES_MAX}",
            name="plan_range",
        ),
        CheckConstraint(
            f"fact_minutes IS NULL OR fact_minutes BETWEEN 0 AND {TRACKED_MINUTES_MAX}",
            name="fact_range",
        ),
        # Обложка — вложение этой же задачи; удаление вложения снимает её (ADR 0064).
        ForeignKeyConstraint(
            ["cover_attachment_id"],
            ["task_attachments.id"],
            name="fk_tasks_cover_attachment_id_task_attachments",
            ondelete="SET NULL",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["id", "cover_attachment_id"],
            ["task_attachments.task_id", "task_attachments.id"],
            name="fk_tasks_cover_of_the_task",
            use_alter=True,
        ),
        # Одна следующая задача на закрытую повторяющуюся (KG-D5).
        Index(
            "uq_tasks_recurred_from",
            "recurred_from_id",
            unique=True,
            postgresql_where=text("recurred_from_id IS NOT NULL"),
        ),
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
    starts_on: Mapped[date | None] = mapped_column(Date)
    due_on: Mapped[date | None] = mapped_column(Date)
    recurrence: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    leo_fields: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    recurred_from_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignee_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    assignee_name: Mapped[str | None] = mapped_column(Text)
    # Проект пространства — мягкая ссылка на `projects` среза workspaces.
    project_id: Mapped[UUID | None] = mapped_column(Uuid)
    source: Mapped[str] = mapped_column(Text, server_default="manual")
    # Встреча — мягкая ссылка: задача, которую тронули, остаётся и после встречи.
    source_meeting_id: Mapped[UUID | None] = mapped_column(Uuid)
    source_finding_id: Mapped[UUID | None] = mapped_column(Uuid)
    # Чат — мягкая ссылка на подключение chats: при отключении она уходит, строка остаётся.
    source_chat_connection_id: Mapped[UUID | None] = mapped_column(Uuid)
    source_chat_messenger: Mapped[str | None] = mapped_column(Text)
    source_chat_title: Mapped[str | None] = mapped_column(Text)
    source_chat_message_url: Mapped[str | None] = mapped_column(Text)
    source_chat_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cover_attachment_id: Mapped[UUID | None] = mapped_column(Uuid)
    # Время задачи (шаг 4a, ревизия `d9f2b4c6e813`): сводка отрезков `task_clock_spans`,
    # пишется вместе с ними под блокировкой задачи, — и таймер, план и факт.
    stopwatch_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopwatch_total_ms: Mapped[int | None] = mapped_column(BigInteger)
    stopwatch_by_column: Mapped[dict[str, int] | None] = mapped_column(JSONB(none_as_null=True))
    timer_length_ms: Mapped[int | None] = mapped_column(BigInteger)
    timer_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timer_paused_left_ms: Mapped[int | None] = mapped_column(BigInteger)
    plan_minutes: Mapped[int | None] = mapped_column(Integer)
    fact_minutes: Mapped[int | None] = mapped_column(Integer)
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
