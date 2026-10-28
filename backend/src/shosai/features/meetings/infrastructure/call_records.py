"""What a call keeps: its chat, its video recordings and its room's board (meetings plan §3.4).

The chat is kept for the call only: handed to notes at its end and deleted, or deleted when
notes are off (MR-D11); a sequence is unique within its call. A recording's row is written
before its egress starts, and only one recording per room is active, by a unique partial
index. The board is one scene per room with its version; the server never reads its
elements, only bounds them.
"""

from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.meetings.domain.board import ELEMENTS_BYTES, ELEMENTS_MAX, FILES_BYTES
from shosai.features.meetings.domain.chat import TEXT_MAX
from shosai.features.meetings.domain.principals import NAME_MAX
from shosai.features.meetings.domain.recordings import RecordingFailure, RecordingState
from shosai.features.meetings.infrastructure.room_records import (
    PRINCIPAL_SHAPE,
    moment,
    room_link,
)

RECORDING_STATES: Final = ", ".join(f"'{state}'" for state in RecordingState)
FAILURES: Final = ", ".join(f"'{failure}'" for failure in RecordingFailure)
ACTIVE: Final = text("state IN ('starting', 'active', 'ending')")


class RoomChatMessageRecord(ModelBase):
    """A message of a call's chat, kept until notes hold it or the call ends without them."""

    __tablename__ = "room_chat_messages"
    __table_args__ = (
        UniqueConstraint("call_id", "seq", name="uq_room_chat_messages_call_seq"),
        CheckConstraint("seq >= 1", name="seq_positive"),
        CheckConstraint(f"principal {PRINCIPAL_SHAPE}", name="principal_shape"),
        CheckConstraint("char_length(identity) BETWEEN 1 AND 100", name="identity_length"),
        CheckConstraint(f"char_length(author) BETWEEN 1 AND {NAME_MAX}", name="author_length"),
        CheckConstraint(f"char_length(body) BETWEEN 1 AND {TEXT_MAX}", name="body_length"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    call_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "room_calls.id", name="fk_room_chat_messages_call_id_room_calls", ondelete="CASCADE"
        ),
    )
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    seq: Mapped[int] = mapped_column(Integer)
    principal: Mapped[str] = mapped_column(Text)
    identity: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = moment(default_now=True)


class RoomRecordingRecord(ModelBase):
    """A video recording of a call: its egress, its object and its end."""

    __tablename__ = "room_recordings"
    __table_args__ = (
        CheckConstraint(f"state IN ({RECORDING_STATES})", name="state_known"),
        CheckConstraint(f"error_code IS NULL OR error_code IN ({FAILURES})", name="error_known"),
        CheckConstraint("(state = 'failed') = (error_code IS NOT NULL)", name="failed_with_code"),
        CheckConstraint(
            "state NOT IN ('complete', 'failed') OR ended_at IS NOT NULL", name="ended_when_over"
        ),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="size_counted"),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0", name="duration_counted"
        ),
        Index("uq_room_recordings_active", "room_id", unique=True, postgresql_where=ACTIVE),
        Index("ix_room_recordings_active", "started_at", postgresql_where=ACTIVE),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    room_id: Mapped[UUID] = room_link("room_recordings")
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    egress_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    state: Mapped[str] = mapped_column(Text, server_default=RecordingState.STARTING.value)
    s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Файл File Manager, которым стала запись: его id — id записи (A7).
    file_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = moment(default_now=True)
    ended_at: Mapped[datetime | None] = moment(nullable=True)


class RoomWhiteboardRecord(ModelBase):
    """A room's board: its scene and images as the editor saved them, with a version."""

    __tablename__ = "room_whiteboards"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(elements) = 'array'", name="elements_list"),
        CheckConstraint("jsonb_typeof(files) = 'object'", name="files_map"),
        CheckConstraint(f"jsonb_array_length(elements) <= {ELEMENTS_MAX}", name="elements_count"),
        CheckConstraint(f"octet_length(elements::text) <= {ELEMENTS_BYTES}", name="elements_size"),
        CheckConstraint(f"octet_length(files::text) <= {FILES_BYTES}", name="files_size"),
        CheckConstraint("version >= 0", name="version_counted"),
        CheckConstraint(f"updated_by {PRINCIPAL_SHAPE}", name="updated_by_shape"),
    )

    room_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("rooms.id", name="fk_room_whiteboards_room_id_rooms", ondelete="CASCADE"),
        primary_key=True,
    )
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    elements: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    files: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    updated_by: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = moment(default_now=True)
