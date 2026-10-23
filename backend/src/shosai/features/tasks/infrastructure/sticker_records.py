"""Stickers, their states, their places on boards and tasks' values (revision `c3e5a7b9d168`).

A sticker is its owner's — a person's, or a workspace's once workspace boards exist — and
company isolation admits it where it admits its owner's rows; its states keep their order.
A board places stickers in order, each shown on its cards or not; the board row keeps the
system fields' visibility and the stopwatch's automations. A task's value is exactly one of
a state of that sticker, a number or a text, and goes with the task, the sticker or the
state.
"""

from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.tasks.infrastructure.board_records import COLORS

KINDS: Final = "'states', 'number', 'text'"


class StickerRecord(ModelBase):
    """A custom sticker of its owner."""

    __tablename__ = "stickers"
    __table_args__ = (
        CheckConstraint(f"kind IN ({KINDS})", name="kind_known"),
        CheckConstraint("length(name) BETWEEN 1 AND 40", name="name_length"),
        Index("ix_stickers_user", "user_id"),
        Index("ix_stickers_org", "org_id", postgresql_where=text("org_id IS NOT NULL")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StickerStateRecord(ModelBase):
    """A state of a set-of-states sticker, in its order."""

    __tablename__ = "sticker_states"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 40", name="name_length"),
        CheckConstraint(f"color IN ({COLORS})", name="color_known"),
        CheckConstraint("position BETWEEN 0 AND 19", name="position_range"),
        UniqueConstraint("sticker_id", "id", name="uq_sticker_states_sticker_state"),
        UniqueConstraint(
            "sticker_id", "position", name="uq_sticker_states_position",
            deferrable=True, initially="DEFERRED",
        ),
    )  # fmt: skip

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    sticker_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("stickers.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    color: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(SmallInteger)


class BoardStickerRecord(ModelBase):
    """A sticker placed on a board, shown on its cards or not."""

    __tablename__ = "board_stickers"
    __table_args__ = (
        CheckConstraint("position BETWEEN 0 AND 19", name="position_range"),
        UniqueConstraint(
            "board_id", "position", name="uq_board_stickers_position",
            deferrable=True, initially="DEFERRED",
        ),
        UniqueConstraint("board_id", "sticker_id", name="uq_board_stickers_placed"),
        Index("ix_board_stickers_sticker", "sticker_id"),
        Index("ix_board_stickers_user", "user_id"),
    )  # fmt: skip

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    board_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("boards.id", ondelete="CASCADE"))
    sticker_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("stickers.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    visible: Mapped[bool] = mapped_column(Boolean, server_default=true())
    position: Mapped[int] = mapped_column(SmallInteger)


class TaskStickerValueRecord(ModelBase):
    """A task's value of a sticker."""

    __tablename__ = "task_sticker_values"
    __table_args__ = (
        CheckConstraint("num_nonnulls(state_id, number, text) = 1", name="one_value"),
        CheckConstraint("text IS NULL OR length(text) BETWEEN 1 AND 200", name="text_length"),
        # Состояние значения — состояние этого же поля; его удаление уносит значение.
        ForeignKeyConstraint(
            ["sticker_id", "state_id"],
            ["sticker_states.sticker_id", "sticker_states.id"],
            name="fk_task_sticker_values_state_of_the_sticker",
            ondelete="CASCADE",
        ),
        UniqueConstraint("task_id", "sticker_id", name="uq_task_sticker_values_value"),
        Index("ix_task_sticker_values_sticker", "sticker_id"),
        Index("ix_task_sticker_values_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"))
    sticker_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("stickers.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    state_id: Mapped[UUID | None] = mapped_column(Uuid)
    number: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    text: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
