"""A task's checklist and its comments in each home (tasks plan §3.4, §3.8, §3.12).

Revision `d5f1b8c3e7a4`.

Children of a task, deleted with it. Each row carries the task's owner and workspace, so
company isolation admits it exactly where it admits the task, and the account data handler
finds a person's rows as it finds their tasks. Subtasks keep their order by fractional keys,
unique at the end of the transaction; comments are paged newest first by their time-ordered
id and name their author, who alone edits or deletes them.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.tasks.infrastructure.board_records import RANK_FORMAT


class TaskSubtaskRecord(ModelBase):
    """A line of a task's checklist."""

    __tablename__ = "task_subtasks"
    __table_args__ = (
        CheckConstraint("length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint(RANK_FORMAT, name="rank_format"),
        UniqueConstraint(
            "task_id", "rank", name="uq_task_subtasks_rank", deferrable=True, initially="DEFERRED"
        ),
        Index("ix_task_subtasks_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(Text)
    done: Mapped[bool] = mapped_column(Boolean, server_default=false())
    rank: Mapped[str] = mapped_column(Text(collation="C"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaskCommentRecord(ModelBase):
    """A comment on a task, by its author."""

    __tablename__ = "task_comments"
    __table_args__ = (
        CheckConstraint("length(body) BETWEEN 1 AND 5000", name="body_length"),
        CheckConstraint("edited_at IS NULL OR edited_at >= created_at", name="edited_after"),
        # Новыми вперёд — обратным проходом по (task_id, id): id упорядочены по времени.
        Index("ix_task_comments_task", "task_id", "id"),
        Index("ix_task_comments_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    author_user_id: Mapped[UUID] = mapped_column(Uuid)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
