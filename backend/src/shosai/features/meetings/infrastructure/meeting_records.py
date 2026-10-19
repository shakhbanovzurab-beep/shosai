"""Meetings, their transcript, speakers and participants in each home (revision `a2c7e4f9b318`).

`sessions` is shareable: `user_id`, `org_id` and `access` as workspaces' access policy reads
them; its children carry `org_id` too, so row-level security's company policy covers every
row. `transcript_segments` is partitioned by the month of its meeting's start: the unique
key of a partitioned table holds its partition key, and the meeting's start is a function
of the meeting, so the key is truly `(session_id, seq)` and a meeting lives in one
partition. Partitions are kept until the transcript archive moves them (plan step 20).
"""

from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    Table,
    Text,
    Uuid,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.access.shareable import ShareableResource
from shosai.core.db.model_base import ModelBase
from shosai.core.db.partitions.policy import monthly_partition_range

ACCESS_CHECKS: Final = (
    "(org_id IS NULL) = (access IS NULL)",
    "access IS NULL OR access IN ('owner', 'selected', 'organization')",
)
MEETING_CASCADE: Final = "CASCADE"


def meeting_reference(*, primary_key: bool = False) -> Mapped[UUID]:
    """The meeting a child row belongs to; it goes with the meeting."""
    return mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete=MEETING_CASCADE), primary_key=primary_key
    )


class MeetingRecord(ModelBase):
    """A recorded meeting of a person or a workspace."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(ACCESS_CHECKS[0], name="org_with_access"),
        CheckConstraint(ACCESS_CHECKS[1], name="access_known"),
        CheckConstraint("org_id IS NULL OR folder_id IS NULL", name="folders_personal"),
        CheckConstraint("status IN ('active', 'completed', 'failed')", name="status_known"),
        CheckConstraint("source IN ('live', 'import')", name="source_known"),
        CheckConstraint("(status = 'active') = (ended_at IS NULL)", name="end_with_status"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="end_after_start"),
        CheckConstraint("length(title) BETWEEN 1 AND 256", name="title_length"),
        CheckConstraint("length(client_device_id) <= 256", name="device_length"),
        CheckConstraint("length(template_id) BETWEEN 1 AND 128", name="template_length"),
        CheckConstraint(
            "seconds >= 0 AND line_count >= 0 AND indexed_upto_seq >= 0 AND notes_revision >= 0",
            name="counters_not_negative",
        ),
        Index("ix_sessions_user_started", "user_id", "started_at"),
        Index("ix_sessions_org", "org_id"),
        Index("ix_sessions_folder", "folder_id"),
        Index("ix_sessions_active", "started_at", postgresql_where=text("status = 'active'")),
        Index(
            "ix_sessions_device",
            "user_id",
            "client_device_id",
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_sessions_hidden", "deleted_at", postgresql_where=text("deleted_at IS NOT NULL")),
        Index(
            "ix_sessions_unsettled",
            "ended_at",
            postgresql_where=text("status <> 'active' AND settled_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    access: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    source: Mapped[str] = mapped_column(Text, server_default="live")
    # Неизменно: по нему выбирается партиция расшифровки.
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seconds: Mapped[int] = mapped_column(Integer, server_default="0")
    client_device_id: Mapped[str | None] = mapped_column(Text)
    # Нет «не хранить мои встречи»: живая расшифровка видна, но не сохраняется (MT-D6).
    kept: Mapped[bool] = mapped_column(Boolean, server_default=true())
    folder_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("meeting_folders.id", ondelete="SET NULL")
    )
    # Встроенный код шаблона или id шаблона человека.
    template_id: Mapped[str | None] = mapped_column(Text)
    line_count: Mapped[int] = mapped_column(Integer, server_default="0")
    indexed_upto_seq: Mapped[int] = mapped_column(Integer, server_default="0")
    notes_revision: Mapped[int] = mapped_column(Integer, server_default="0")
    latest_run_id: Mapped[UUID | None] = mapped_column(Uuid)
    # Расшифровка закончившейся встречи сверена с показанной, прогон заведён (inv-6, inv-7);
    # строка, слитая позже, снимает отметку (ревизия `b4e8f2a6c913`).
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Сколько показанных строк встреча недосчиталась при прошлом досчёте (inv-6).
    lines_missing: Mapped[int] = mapped_column(Integer, server_default="0")
    # Удалённая встреча скрыта 7 дней (MT-D8).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TranscriptLineRecord(ModelBase):
    """A transcript line, `(session_id, seq)`, in the partition of its meeting's month."""

    __tablename__ = "transcript_segments"
    __table_args__ = (
        PrimaryKeyConstraint(
            "session_id", "seq", "meeting_started_at", name="pk_transcript_segments"
        ),
        CheckConstraint("seq >= 1", name="seq_from_one"),
        CheckConstraint("start_ms >= 0 AND duration_ms >= 0", name="times_not_negative"),
        CheckConstraint("length(text) <= 20000", name="text_length"),
        CheckConstraint("origin IN ('live', 'recording')", name="origin_known"),
        CheckConstraint("speaker_idx IS NULL OR speaker_idx >= 0", name="speaker_not_negative"),
        Index("ix_transcript_segments_order", "session_id", "start_ms", "seq"),
        {"postgresql_partition_by": monthly_partition_range("meeting_started_at")},
    )

    session_id: Mapped[UUID] = meeting_reference()
    seq: Mapped[int] = mapped_column(Integer)
    # Копия начала встречи: ключ партиции.
    meeting_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    # Начало фразы; смещение от начала встречи — `start_ms`.
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    start_ms: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    speaker_idx: Mapped[int | None] = mapped_column(SmallInteger)
    text: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text, server_default="live")
    run_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpeakerRecord(ModelBase):
    """A speaker of a meeting by its number."""

    __tablename__ = "meeting_speakers"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'other', 'numbered')", name="role_known"),
        CheckConstraint("idx >= 0 AND talk_ms >= 0", name="numbers_not_negative"),
        Index("uq_meeting_speakers_number", "session_id", "idx", unique=True),
        Index("ix_meeting_speakers_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = meeting_reference()
    # Владелец встречи, денормализован для выгрузки и переноса аккаунта.
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    idx: Mapped[int] = mapped_column(SmallInteger)
    role: Mapped[str] = mapped_column(Text, server_default="numbered")
    talk_ms: Mapped[int] = mapped_column(Integer, server_default="0")
    # Человек из commitments, когда тот срез его узнает.
    person_id: Mapped[UUID | None] = mapped_column(Uuid)


class ParticipantRecord(ModelBase):
    """A participant of a meeting: an address, a name, or both."""

    __tablename__ = "meeting_participants"
    __table_args__ = (
        CheckConstraint("source IN ('added', 'calendar', 'speaker')", name="source_known"),
        CheckConstraint("email IS NOT NULL OR name IS NOT NULL", name="someone"),
        CheckConstraint("length(email) BETWEEN 3 AND 254", name="email_length"),
        CheckConstraint("length(name) BETWEEN 1 AND 200", name="name_length"),
        Index(
            "uq_meeting_participants_email",
            "session_id",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index("ix_meeting_participants_session", "session_id"),
        Index("ix_meeting_participants_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = meeting_reference()
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    email: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, server_default="added")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Вид ресурса для политики доступа workspaces: личная встреча публикуется записью шаринга.
MEETING_RESOURCE: Final = ShareableResource("meeting", cast("Table", MeetingRecord.__table__))
