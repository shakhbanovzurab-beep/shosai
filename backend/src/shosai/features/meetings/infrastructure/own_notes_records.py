"""A person's own notes on a meeting, one row per meeting and person (revision `e5c2a8d4f017`).

Whoever may read a meeting keeps notes of their own on it, synced with the desktop: their
row, `user_id` theirs, read and written by them alone — the meeting's owner never sees a
member's notes, nor a member the owner's — and never published by a share link. The
table is personal by nature: row-level security admits a row to its writer only. A row
goes with its meeting.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.meetings.infrastructure.meeting_records import meeting_reference


class OwnNotesRecord(ModelBase):
    """A person's own notes on a meeting: the text, its version and the last writing client."""

    __tablename__ = "meeting_own_notes"
    __table_args__ = (
        CheckConstraint("octet_length(markdown) <= 262144", name="size"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("client IN ('web', 'macos', 'windows')", name="client_known"),
        Index("uq_meeting_own_notes_person", "session_id", "user_id", unique=True),
        Index("ix_meeting_own_notes_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = meeting_reference()
    # Тот, чьи это заметки, — не обязательно владелец встречи.
    user_id: Mapped[UUID] = mapped_column(Uuid)
    markdown: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    client: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
