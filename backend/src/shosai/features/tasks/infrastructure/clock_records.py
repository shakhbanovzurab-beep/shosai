"""The stopwatch's spans (revision `d9f2b4c6e813`, tasks plan §3.9).

A span is a stretch the task's stopwatch ran, in the column of the board where it ran — a
soft reference, as a column may go while its time stays — or unplaced. It carries the
task's owner and workspace like every row hanging on a task, and goes with the task. A
partial unique index keeps one running span per task, also under concurrent calls.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase


class TaskClockSpanRecord(ModelBase):
    """A stretch the task's stopwatch ran; open while it runs."""

    __tablename__ = "task_clock_spans"
    __table_args__ = (
        CheckConstraint("stopped_at IS NULL OR stopped_at >= started_at", name="ordered"),
        Index(
            "uq_task_clock_spans_running",
            "task_id",
            unique=True,
            postgresql_where=text("stopped_at IS NULL"),
        ),
        Index("ix_task_clock_spans_task", "task_id", "started_at"),
        Index("ix_task_clock_spans_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    column_id: Mapped[UUID | None] = mapped_column(Uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
