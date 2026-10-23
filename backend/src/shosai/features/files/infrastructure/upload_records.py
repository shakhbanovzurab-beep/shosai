"""Uploads, a person's storage usage and pending object deletions (revision `e7b2c5d9a314`).

Revision `f2b8d4a6c931` adds the purpose `task_attachment` (ADR 0064).

Uploads and usage are personal. An upload reserves its declared bytes while pending or
ready. `object_deletions` names keys whose last row is gone, until the bucket confirms.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    Text,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

PURPOSES = (
    "'file_manager', 'recording', 'leo_attachment', 'ticket_attachment', 'workspace_upload', "
    "'app_build', 'task_attachment'"
)
STATES = "'pending', 'ready', 'claimed', 'rejected', 'expired'"


class UploadRecord(ModelBase):
    """An upload straight to the bucket, from creation to its claim."""

    __tablename__ = "uploads"
    __table_args__ = (
        CheckConstraint(f"purpose IN ({PURPOSES})", name="purpose_known"),
        CheckConstraint(f"state IN ({STATES})", name="state_known"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("length(filename) BETWEEN 1 AND 255", name="filename_length"),
        CheckConstraint("length(content_type) BETWEEN 1 AND 255", name="type_length"),
        CheckConstraint("length(object_key) BETWEEN 1 AND 1024", name="key_length"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        Index("ix_uploads_user", "user_id"),
        Index(
            "ix_uploads_open",
            "expires_at",
            postgresql_where=text("state IN ('pending', 'ready')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    purpose: Mapped[str] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text)
    multipart_id: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StorageUsageRecord(ModelBase):
    """A person's stored and reserved bytes, their time over the storage limit (FL-D2) and
    Leo's time over the knowledge limit (FL-D10)."""

    __tablename__ = "storage_usage"
    __table_args__ = (
        CheckConstraint("used_bytes >= 0 AND reserved_bytes >= 0", name="not_negative"),
        CheckConstraint("reminders_sent BETWEEN 0 AND 3", name="reminders_range"),
        CheckConstraint(
            "over_limit_since IS NOT NULL OR reminders_sent = 0", name="reminders_while_over"
        ),
        CheckConstraint("leo_reminders_sent BETWEEN 0 AND 3", name="leo_reminders_range"),
        CheckConstraint(
            "leo_over_limit_since IS NOT NULL OR leo_reminders_sent = 0",
            name="leo_reminders_while_over",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    used_bytes: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    over_limit_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminders_sent: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    leo_over_limit_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    leo_reminders_sent: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    # Окно удаления аккаунта и время последнего применённого события identity (шаг 7).
    account_hidden: Mapped[bool] = mapped_column(Boolean, server_default=false())
    account_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ObjectDeletionRecord(ModelBase):
    """A key whose last row is gone, deleted from the bucket after that commit."""

    __tablename__ = "object_deletions"
    __table_args__ = (CheckConstraint("length(object_key) BETWEEN 1 AND 1024", name="key_length"),)

    object_key: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
