"""Objects files holds for other slices (revision `f2b8d4a6c931`, ADR 0064).

A held object is a task's attachment's bytes: its key in the owner's prefix — its own, or a
File Manager file's it shares (FL-D4) — its preview's key and its facts. Company isolation
admits a row where it admits the holder's; the holder names it by id. One upload makes at
most one held object, so a repeated attachment of the same upload holds it once.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

HOLDERS: Final = "'task_attachment'"
PREVIEW_STATES: Final = "'none', 'pending', 'made', 'failed'"


class HeldObjectRecord(ModelBase):
    """An object another slice holds through files."""

    __tablename__ = "held_objects"
    __table_args__ = (
        CheckConstraint(f"holder IN ({HOLDERS})", name="holder_known"),
        CheckConstraint(f"preview_state IN ({PREVIEW_STATES})", name="preview_state_known"),
        CheckConstraint(
            "(preview_state = 'made') = (preview_key IS NOT NULL)", name="preview_when_made"
        ),
        CheckConstraint("length(filename) BETWEEN 1 AND 500", name="filename_length"),
        CheckConstraint("length(content_type) BETWEEN 1 AND 255", name="type_length"),
        CheckConstraint("size_bytes >= 0", name="size_not_negative"),
        CheckConstraint("length(object_key) BETWEEN 1 AND 1024", name="key_length"),
        Index("ix_held_objects_user", "user_id"),
        Index("ix_held_objects_org", "org_id", postgresql_where=text("org_id IS NOT NULL")),
        Index("ix_held_objects_object_key", "object_key"),
        Index(
            "ix_held_objects_preview_key",
            "preview_key",
            postgresql_where=text("preview_key IS NOT NULL"),
        ),
        Index(
            "uq_held_objects_upload",
            "upload_id",
            unique=True,
            postgresql_where=text("upload_id IS NOT NULL"),
        ),
        Index(
            "ix_held_objects_preview_pending",
            "created_at",
            postgresql_where=text("preview_state = 'pending'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    holder: Mapped[str] = mapped_column(Text)
    upload_id: Mapped[UUID | None] = mapped_column(Uuid)
    object_key: Mapped[str] = mapped_column(Text)
    preview_key: Mapped[str | None] = mapped_column(Text)
    preview_state: Mapped[str] = mapped_column(Text, server_default="none")
    filename: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
