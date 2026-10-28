"""What a broadcast keeps: the broadcast, its stage, its bans and its chat (meetings plan §3.4).

The draft's columns are kept so its rows move unchanged (DATA_MAPPING §5.21); every row also
carries the owner and the space of the broadcast's room, as every meetings table does. A
broadcast owns one room — the SFU's room, the recording's anchor — and the room serves no
call besides it. The audience has no table: who watches now is the SFU's to know, and what
outlives the broadcast is its chat. Raised hands and the waiting room live in Valkey for 20
and 10 minutes; nothing of them survives the window.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.meetings.domain.broadcasts import SPEAKERS_MAX, BroadcastState, StageRole
from shosai.features.meetings.domain.chat import TEXT_MAX
from shosai.features.meetings.domain.principals import NAME_MAX
from shosai.features.meetings.domain.rooms import TITLE_MAX
from shosai.features.meetings.infrastructure.room_records import PRINCIPAL_SHAPE, moment, room_link

STATES: Final = ", ".join(f"'{state}'" for state in BroadcastState)
ROLES: Final = ", ".join(f"'{role}'" for role in StageRole)
DESCRIPTION_MAX: Final = 2_000
# Предел сцены черновика: ведущий может сузить её, но не шире 20 мест.
SPEAKER_LIMIT_MAX: Final = 20


def stream_link(table: str) -> Mapped[UUID]:
    """The broadcast a child row belongs to, deleted with it."""
    return mapped_column(
        Uuid, ForeignKey("streams.id", name=f"fk_{table}_stream_id_streams", ondelete="CASCADE")
    )


class StreamRecord(ModelBase):
    """A broadcast: its room, its state and the host's settings."""

    __tablename__ = "streams"
    __table_args__ = (
        CheckConstraint(f"status IN ({STATES})", name="status_known"),
        CheckConstraint(f"char_length(title) BETWEEN 1 AND {TITLE_MAX}", name="title_length"),
        CheckConstraint(
            f"char_length(description) <= {DESCRIPTION_MAX}", name="description_length"
        ),
        CheckConstraint(
            f"speaker_limit BETWEEN 1 AND {SPEAKER_LIMIT_MAX}", name="speaker_limit_range"
        ),
        CheckConstraint("chat_mode IN ('everyone', 'speakers', 'off')", name="chat_mode_known"),
        CheckConstraint(
            "stage_mode IN ('grid', 'spotlight', 'presentation')", name="stage_mode_known"
        ),
        CheckConstraint("status = 'scheduled' OR started_at IS NOT NULL", name="started_when_live"),
        CheckConstraint("(status = 'ended') = (ended_at IS NOT NULL)", name="ended_when_ended"),
        CheckConstraint(
            f"pinned_principal IS NULL OR pinned_principal {PRINCIPAL_SHAPE}", name="pinned_shape"
        ),
        UniqueConstraint("room_id", name="uq_streams_room_id"),
        Index("ix_streams_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    room_id: Mapped[UUID] = room_link("streams")
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(Text, server_default=BroadcastState.SCHEDULED.value)
    started_at: Mapped[datetime | None] = moment(nullable=True)
    ended_at: Mapped[datetime | None] = moment(nullable=True)
    speaker_limit: Mapped[int] = mapped_column(Integer, server_default=str(SPEAKERS_MAX))
    registered_only: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # Зал ожидания: зрителя впускает ведущий или соведущий.
    manual_admit: Mapped[bool] = mapped_column(Boolean, server_default="false")
    chat_mode: Mapped[str] = mapped_column(Text, server_default="everyone")
    reactions_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    requests_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    save_chat: Mapped[bool] = mapped_column(Boolean, server_default="true")
    stage_mode: Mapped[str] = mapped_column(Text, server_default="grid")
    pinned_principal: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = moment(default_now=True)
    updated_at: Mapped[datetime] = moment(default_now=True)


class StreamMemberRecord(ModelBase):
    """A place on the stage: the host, a co-host or a speaker, on air or off it."""

    __tablename__ = "stream_members"
    __table_args__ = (
        CheckConstraint(f"role IN ({ROLES})", name="role_known"),
        CheckConstraint(f"principal {PRINCIPAL_SHAPE}", name="principal_shape"),
        CheckConstraint(
            f"char_length(display_name) BETWEEN 1 AND {NAME_MAX}", name="display_name_length"
        ),
        CheckConstraint("position >= 0", name="position_counted"),
        UniqueConstraint("stream_id", "principal", name="uq_stream_members_stream_principal"),
        Index("ix_stream_members_stage", "stream_id", "position"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    stream_id: Mapped[UUID] = stream_link("stream_members")
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    principal: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, server_default=StageRole.SPEAKER.value)
    on_air: Mapped[bool] = mapped_column(Boolean, server_default="true")
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = moment(default_now=True)
    updated_at: Mapped[datetime] = moment(default_now=True)


class StreamBanRecord(ModelBase):
    """A principal the host sent out of the broadcast for good."""

    __tablename__ = "stream_bans"
    __table_args__ = (
        CheckConstraint(f"principal {PRINCIPAL_SHAPE}", name="principal_shape"),
        CheckConstraint(f"banned_by {PRINCIPAL_SHAPE}", name="banned_by_shape"),
        UniqueConstraint("stream_id", "principal", name="uq_stream_bans_stream_principal"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    stream_id: Mapped[UUID] = stream_link("stream_bans")
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    principal: Mapped[str] = mapped_column(Text)
    banned_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = moment(default_now=True)
    updated_at: Mapped[datetime] = moment(default_now=True)


class StreamChatMessageRecord(ModelBase):
    """A message of the broadcast's chat, numbered within it; the stage's are marked."""

    __tablename__ = "stream_chat_messages"
    __table_args__ = (
        CheckConstraint("seq >= 1", name="seq_positive"),
        CheckConstraint(f"principal {PRINCIPAL_SHAPE}", name="principal_shape"),
        CheckConstraint(f"char_length(author) BETWEEN 1 AND {NAME_MAX}", name="author_length"),
        CheckConstraint(f"char_length(body) BETWEEN 1 AND {TEXT_MAX}", name="body_length"),
        UniqueConstraint("stream_id", "seq", name="uq_stream_chat_messages_stream_seq"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    stream_id: Mapped[UUID] = stream_link("stream_chat_messages")
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    seq: Mapped[int] = mapped_column(Integer)
    principal: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(Boolean, server_default="false")
    from_stage: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = moment(default_now=True)
    updated_at: Mapped[datetime] = moment(default_now=True)
    deleted_at: Mapped[datetime | None] = moment(nullable=True)
