"""Post-meeting runs and objects waiting for deletion, in each home (revision `a2c7e4f9b318`).

A run is one source's work on a meeting, unique by `(session_id, idempotency_key)`, with
the state of each stage in `stage_state`. It points at its transient objects — the
recording, the raw recognition, the speaker turns — which live at most 72 hours.
`meeting_object_deletions` names keys whose rows are gone until the bucket confirms their
deletion; it holds keys only, nothing personal.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.meetings.infrastructure.meeting_records import meeting_reference


class RunRecord(ModelBase):
    """A post-meeting run with its stages and transient objects."""

    __tablename__ = "meeting_processing_runs"
    __table_args__ = (
        CheckConstraint(
            "source IN ('live', 'import', 'recording', 'regenerate')", name="source_known"
        ),
        CheckConstraint(
            "state IN ('pending', 'running', 'succeeded', 'partially_completed', 'failed')",
            name="state_known",
        ),
        CheckConstraint("length(idempotency_key) BETWEEN 1 AND 200", name="key_length"),
        CheckConstraint("jsonb_typeof(stage_state) = 'object'", name="stages_object"),
        CheckConstraint(
            "audio_size_bytes IS NULL OR audio_size_bytes >= 0", name="audio_size_not_negative"
        ),
        CheckConstraint(
            "audio_duration_ms IS NULL OR audio_duration_ms >= 0", name="audio_length_not_negative"
        ),
        CheckConstraint("length(error_code) BETWEEN 1 AND 64", name="error_code_length"),
        CheckConstraint("layout IS NULL OR jsonb_typeof(layout) = 'object'", name="layout_object"),
        Index("uq_meeting_processing_runs_key", "session_id", "idempotency_key", unique=True),
        Index("ix_meeting_processing_runs_user", "user_id"),
        Index(
            "ix_meeting_processing_runs_open",
            "updated_at",
            postgresql_where=text("state IN ('pending', 'running')"),
        ),
        Index(
            "ix_meeting_processing_runs_objects",
            "audio_expires_at",
            postgresql_where=text("audio_key IS NOT NULL OR raw_transcript_key IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = meeting_reference()
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    source: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="pending")
    stage_state: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # Временные объекты прогона в бакете дома, не дольше 72 часов.
    audio_key: Mapped[str | None] = mapped_column(Text)
    multipart_id: Mapped[str | None] = mapped_column(Text)
    audio_content_type: Mapped[str | None] = mapped_column(Text)
    audio_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    audio_duration_ms: Mapped[int | None] = mapped_column(Integer)
    # Смещение начала записи от начала встречи, его шлют десктопы (MT-D3).
    audio_lead_ms: Mapped[int | None] = mapped_column(Integer)
    audio_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_transcript_key: Mapped[str | None] = mapped_column(Text)
    turns_key: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    # Раскладка, которую человек выбрал для переписывания: шаблон и его секции на момент запроса.
    layout: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ObjectDeletionRecord(ModelBase):
    """A key whose rows are gone, until the bucket confirms its deletion."""

    __tablename__ = "meeting_object_deletions"
    __table_args__ = (CheckConstraint("length(object_key) BETWEEN 1 AND 1024", name="key_length"),)

    object_key: Mapped[str] = mapped_column(Text, primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
