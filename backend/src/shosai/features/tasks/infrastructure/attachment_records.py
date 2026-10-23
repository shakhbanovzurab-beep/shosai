"""A task's attachments and the queue of held objects to give back (revision `a4c6e8b2d397`).

An attachment names the object files holds for it (ADR 0064), one attachment per held
object, with the facts its card and panel show; it carries the task's owner and workspace,
so company isolation admits it where it admits the task, and goes with the task. Every
deleted attachment leaves its held object in `task_attachment_releases` by the database's
trigger, until tasks gives it back to files.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase


class TaskAttachmentRecord(ModelBase):
    """A file of a task."""

    __tablename__ = "task_attachments"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 500", name="name_length"),
        CheckConstraint("length(content_type) BETWEEN 1 AND 255", name="type_length"),
        CheckConstraint("size_bytes >= 0", name="size_not_negative"),
        UniqueConstraint("held_object_id", name="uq_task_attachments_held_object_id"),
        # Цель пары ключей обложки: вложение той же задачи.
        UniqueConstraint("task_id", "id", name="uq_task_attachments_task_id"),
        Index("ix_task_attachments_task_added", "task_id", "added_at"),
        Index("ix_task_attachments_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    held_object_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    image: Mapped[bool] = mapped_column(Boolean)
    added_by: Mapped[UUID] = mapped_column(Uuid)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaskAttachmentReleaseRecord(ModelBase):
    """A held object no attachment names any more, waiting to go back to files."""

    __tablename__ = "task_attachment_releases"
    __table_args__ = (Index("ix_task_attachment_releases_user", "user_id"),)

    held_object_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
