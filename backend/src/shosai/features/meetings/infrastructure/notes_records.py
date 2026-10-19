"""A meeting's notes and findings; a person's folders, templates and settings (`a2c7e4f9b318`).

`meeting_notes` holds Leo's write-up as sections over the findings of one run and the map
projected from them (`findings_run_id`, `d9f3b7a1c246`); each person's own notes are rows of
`meeting_own_notes` (`e5c2a8d4f017`). `meeting_findings` holds each run's findings with
their evidence. Folders, templates and the no-logs setting are personal by nature and
never shared.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    Text,
    Uuid,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.meetings.infrastructure.meeting_records import meeting_reference


class NotesRecord(ModelBase):
    """The notes of one meeting: Leo's write-up and the map."""

    __tablename__ = "meeting_notes"
    __table_args__ = (
        CheckConstraint(
            "write_up IS NULL OR jsonb_typeof(write_up) = 'object'", name="write_up_object"
        ),
        CheckConstraint("map IS NULL OR jsonb_typeof(map) = 'object'", name="map_object"),
        CheckConstraint("length(write_up_template) BETWEEN 1 AND 128", name="template_length"),
        Index("ix_meeting_notes_user", "user_id"),
    )

    session_id: Mapped[UUID] = meeting_reference(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    # Пустое значение — SQL NULL, а не JSON null: так его и проверяет схема.
    write_up: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    write_up_template: Mapped[str | None] = mapped_column(Text)
    write_up_run_id: Mapped[UUID | None] = mapped_column(Uuid)
    # Прогон, чьи находки перечисляет запись: переписывание оставляет прежние находки и их id.
    findings_run_id: Mapped[UUID | None] = mapped_column(Uuid)
    # Запись Leo, которую человек не выбирал и не переписывал: её перепишет запись с десктопа.
    write_up_automatic: Mapped[bool] = mapped_column(Boolean, server_default=true())
    write_up_written_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    map: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FindingRecord(ModelBase):
    """A finding of a meeting's notes revision, with its evidence."""

    __tablename__ = "meeting_findings"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('key_point', 'decision', 'action_item', 'promise', 'risk', 'question')",
            name="kind_known",
        ),
        CheckConstraint("length(text) BETWEEN 1 AND 500", name="text_length"),
        CheckConstraint("length(topic) BETWEEN 1 AND 80", name="topic_length"),
        CheckConstraint("length(owner_name) BETWEEN 1 AND 120", name="owner_length"),
        CheckConstraint("length(quote) <= 300", name="quote_length"),
        CheckConstraint("0 <= start_ms AND start_ms <= end_ms", name="evidence_span"),
        CheckConstraint("revision >= 1 AND position >= 0", name="order_known"),
        CheckConstraint("owner_speaker IS NULL OR owner_speaker >= 0", name="owner_not_negative"),
        Index("ix_meeting_findings_revision", "session_id", "revision", "position"),
        Index("ix_meeting_findings_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = meeting_reference()
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    run_id: Mapped[UUID] = mapped_column(Uuid)
    revision: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(Text)
    owner_speaker: Mapped[int | None] = mapped_column(SmallInteger)
    owner_name: Mapped[str | None] = mapped_column(Text)
    due_on: Mapped[date | None] = mapped_column(Date)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FolderRecord(ModelBase):
    """A person's flat folder of meetings."""

    __tablename__ = "meeting_folders"
    __table_args__ = (
        # Новые имена — до 40 символов; длиннее — папки черновика, сплющенные M1 (MT-D7).
        CheckConstraint("length(name) BETWEEN 1 AND 200", name="name_length"),
        CheckConstraint("color IN ('green', 'violet', 'red', 'blue', 'amber')", name="color_known"),
        Index("ix_meeting_folders_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    color: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TemplateRecord(ModelBase):
    """A person's template of the write-up."""

    __tablename__ = "meeting_templates"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 120", name="name_length"),
        CheckConstraint("length(description) BETWEEN 1 AND 300", name="description_length"),
        CheckConstraint(
            "icon IN ('briefcase', 'chart', 'handshake', 'landmark', 'lightbulb', 'magnet', "
            "'phone', 'rocket', 'calendar', 'users')",
            name="icon_known",
        ),
        CheckConstraint("jsonb_typeof(sections) = 'array'", name="sections_array"),
        Index("ix_meeting_templates_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(Text)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SettingsRecord(ModelBase):
    """A person's meetings setting (MT-D6) and whether their account waits for its erasure."""

    __tablename__ = "meeting_settings"

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    keep_meetings: Mapped[bool] = mapped_column(Boolean, server_default=true())
    # Окно удаления аккаунта identity (`f2b6d1c9a473`): поддержка не видит и не восстанавливает.
    account_hidden: Mapped[bool] = mapped_column(Boolean, server_default=false())
    # Время последнего применённого события окна: старое событие ничего не меняет.
    account_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
