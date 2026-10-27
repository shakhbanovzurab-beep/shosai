"""Rooms, their calls and their bans in each home (meetings plan §3.4).

A room lives in its owner's home with the owner and the space it was opened in; every child
row repeats both, so row-level security reads them without a join. A room and its children
are visible to their owner only, within the owner's spaces (inv-14): a link's guest acts
through meetings' routes, which open the owner's scope for that room. PostgreSQL keeps every
closed set, the token's and the LiveKit name's shapes, the close that comes with a closed
room, and one call per SFU room instance.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.meetings.domain.calls import CallState
from shosai.features.meetings.domain.rooms import TITLE_MAX, ClosedBy, RoomState

ROOM_STATES: Final = ", ".join(f"'{state}'" for state in RoomState)
CLOSERS: Final = ", ".join(f"'{closer}'" for closer in ClosedBy)
CALL_STATES: Final = ", ".join(f"'{state}'" for state in CallState)
# Форма токена и имени LiveKit — та же, что в домене: новые и перенесённые черновиком.
INVITE_SHAPE: Final = "invite_token ~ '^[A-Za-z0-9_-]{12,64}$'"
LIVEKIT_SHAPE: Final = "lk_room_name ~ '^r-[0-9a-f]{8,64}$'"
PRINCIPAL_SHAPE: Final = (
    "~ '^(guest-[0-9a-f]{12}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$'"
)
OPEN: Final = text("state = 'open'")
NOT_ENDED: Final = text("state <> 'ended'")
CEILING_MAX: Final = 1_000


def moment(*, default_now: bool = False, nullable: bool = False) -> Mapped[datetime]:
    """A timestamp column, defaulting to now when asked."""
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now() if default_now else None,
        nullable=nullable,
    )


def room_link(table: str) -> Mapped[UUID]:
    """The room a child row belongs to, deleted with it."""
    return mapped_column(
        Uuid, ForeignKey("rooms.id", name=f"fk_{table}_room_id_rooms", ondelete="CASCADE")
    )


class RoomRecord(ModelBase):
    """A room opened by "New meeting", reached by its one link."""

    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint(f"state IN ({ROOM_STATES})", name="state_known"),
        CheckConstraint(f"closed_by IS NULL OR closed_by IN ({CLOSERS})", name="closer_known"),
        CheckConstraint(
            "(state = 'closed') = (closed_at IS NOT NULL)", name="closed_with_its_close"
        ),
        CheckConstraint("(closed_at IS NULL) = (closed_by IS NULL)", name="closer_with_time"),
        CheckConstraint(
            f"title IS NULL OR char_length(title) BETWEEN 1 AND {TITLE_MAX}", name="title_length"
        ),
        CheckConstraint(INVITE_SHAPE, name="invite_token_shape"),
        CheckConstraint(LIVEKIT_SHAPE, name="lk_room_name_shape"),
        CheckConstraint(
            "event_ref IS NULL OR char_length(event_ref) BETWEEN 1 AND 200", name="event_ref_length"
        ),
        Index("ix_rooms_owner_open", "owner_id", "created_at", postgresql_where=OPEN),
        Index("ix_rooms_open", "created_at", "id", postgresql_where=OPEN),
        Index(
            "uq_rooms_owner_event",
            "owner_id",
            "event_ref",
            unique=True,
            postgresql_where=text("event_ref IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    lk_room_name: Mapped[str] = mapped_column(Text, unique=True)
    invite_token: Mapped[str] = mapped_column(Text, unique=True)
    state: Mapped[str] = mapped_column(Text, server_default=RoomState.OPEN.value)
    notes_on: Mapped[bool] = mapped_column(Boolean, server_default=true())
    closed_at: Mapped[datetime | None] = moment(nullable=True)
    closed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Событие календаря, для которого открыта комната (B5); одно на владельца.
    event_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = moment(default_now=True)
    updated_at: Mapped[datetime] = moment(default_now=True)


class RoomCallRecord(ModelBase):
    """One life of a room in the SFU, keyed by the SFU room's sid."""

    __tablename__ = "room_calls"
    __table_args__ = (
        CheckConstraint(f"state IN ({CALL_STATES})", name="state_known"),
        CheckConstraint("(state = 'live') = (emptied_at IS NULL)", name="emptied_when_finished"),
        CheckConstraint("(state = 'ended') = (ended_at IS NOT NULL)", name="ended_when_ended"),
        CheckConstraint(f"ceiling BETWEEN 2 AND {CEILING_MAX}", name="ceiling_range"),
        CheckConstraint("peak_participants >= 0", name="peak_counted"),
        Index("ix_room_calls_room", "room_id", "started_at"),
        Index("ix_room_calls_unended", "room_id", postgresql_where=NOT_ENDED),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    room_id: Mapped[UUID] = room_link("room_calls")
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    lk_room_sid: Mapped[str] = mapped_column(Text, unique=True)
    state: Mapped[str] = mapped_column(Text, server_default=CallState.LIVE.value)
    started_at: Mapped[datetime] = moment()
    emptied_at: Mapped[datetime | None] = moment(nullable=True)
    ended_at: Mapped[datetime | None] = moment(nullable=True)
    ceiling: Mapped[int] = mapped_column(Integer)
    peak_participants: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # Встреча владельца в «Заметках» (B2) и последняя картинка доски (A11b).
    meeting_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    board_upload_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)


class RoomBanRecord(ModelBase):
    """A principal the owner removed: refused on every path into this room."""

    __tablename__ = "room_bans"
    __table_args__ = (
        UniqueConstraint("room_id", "principal", name="uq_room_bans_room_principal"),
        CheckConstraint(f"principal {PRINCIPAL_SHAPE}", name="principal_shape"),
        CheckConstraint(f"banned_by {PRINCIPAL_SHAPE}", name="banned_by_shape"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    room_id: Mapped[UUID] = room_link("room_bans")
    principal: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    banned_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = moment(default_now=True)
