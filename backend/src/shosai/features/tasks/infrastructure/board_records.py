"""A person's boards, their columns, where tasks sit on them, and the incoming board (§3.4).

Personal by nature: row-level security admits a person's own rows only, and every row
carries its person. A column belongs to its board, and a card sits in a column of its own
board — the composite key holds both. A task sits on at most one of a person's boards; the
same workspace task may sit on another member's board, as that member's row. Positions of
columns and ranks of cards are unique where they order, checked at the end of the
transaction, so a layout or a column's re-spacing rewrites many rows at once.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

ICONS: Final = (
    "'briefcase', 'home', 'user', 'heart', 'graduation-cap', 'plane', 'shopping-cart', "
    "'dumbbell', 'rocket', 'book'"
)
KINDS: Final = "'todo', 'in_progress', 'done'"
COLORS: Final = "'gray', 'red', 'orange', 'amber', 'green', 'teal', 'blue', 'violet', 'pink'"
SYSTEM_VISIBILITY: Final = text(
    '\'{"assignee": true, "due": true, "priority": true, "recurrence": false, '
    '"stopwatch": false, "timer": false, "time_tracking": false}\'::jsonb'
)
AUTOMATIONS: Final = text(
    '\'{"start_on_arrival": false, "restart_on_move": true, "stop_on_done": true}\'::jsonb'
)
# Ключ порядка — цифры base-62 без нуля в конце; длиннее 48 знаков колонку перераскладывают.
RANK_FORMAT: Final = "rank ~ '^[0-9A-Za-z]*[1-9A-Za-z]$' AND length(rank) <= 128"


class BoardRecord(ModelBase):
    """A person's board."""

    __tablename__ = "boards"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 60", name="name_length"),
        CheckConstraint(f"icon IN ({ICONS})", name="icon_known"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        Index("ix_boards_user", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(BigInteger, server_default="1")
    # Видимость системных полей и автоматизации секундомера (шаг 4s, ревизия `c3e5a7b9d168`).
    system_stickers: Mapped[dict[str, bool]] = mapped_column(
        JSONB, server_default=SYSTEM_VISIBILITY
    )
    stopwatch_automations: Mapped[dict[str, bool]] = mapped_column(
        JSONB, server_default=AUTOMATIONS
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BoardColumnRecord(ModelBase):
    """A column of a board: its title, kind and place from the left."""

    __tablename__ = "board_columns"
    __table_args__ = (
        CheckConstraint("length(title) BETWEEN 1 AND 60", name="title_length"),
        CheckConstraint(f"kind IN ({KINDS})", name="kind_known"),
        CheckConstraint("position BETWEEN 0 AND 19", name="position_range"),
        CheckConstraint(f"color IS NULL OR color IN ({COLORS})", name="color_known"),
        UniqueConstraint(
            "board_id",
            "position",
            name="uq_board_columns_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        # Ключ для карточек: колонка карточки — колонка её доски.
        UniqueConstraint("board_id", "id", name="uq_board_columns_board_column"),
        Index("ix_board_columns_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    board_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("boards.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    # Вид человека на свою доску (шаг 4, ревизия `b7d1f3a9c524`).
    color: Mapped[str | None] = mapped_column(Text)
    collapsed: Mapped[bool] = mapped_column(Boolean, server_default=false())


class TaskPlacementRecord(ModelBase):
    """Where a task sits on one of a person's boards, and its order in the column."""

    __tablename__ = "task_placements"
    __table_args__ = (
        CheckConstraint(RANK_FORMAT, name="rank_format"),
        # NO ACTION, а не RESTRICT: удаление доски каскадом уносит и колонки, и карточки за один
        # оператор; удалить колонку с карточками прямо по-прежнему нельзя.
        ForeignKeyConstraint(
            ["board_id", "column_id"],
            ["board_columns.board_id", "board_columns.id"],
            name="fk_task_placements_board_id_board_columns",
        ),
        UniqueConstraint(
            "board_id",
            "column_id",
            "rank",
            name="uq_task_placements_rank",
            deferrable=True,
            initially="DEFERRED",
        ),
        Index("ix_task_placements_task", "task_id"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    board_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("boards.id", ondelete="CASCADE"))
    column_id: Mapped[UUID] = mapped_column(Uuid)
    rank: Mapped[str] = mapped_column(Text(collation="C"))
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaskSettingsRecord(ModelBase):
    """A person's settings of tasks: the board incoming work lands on (TK-D4)."""

    __tablename__ = "task_settings"
    __table_args__ = (
        Index(
            "ix_task_settings_incoming_board",
            "incoming_board_id",
            postgresql_where=text("incoming_board_id IS NOT NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    incoming_board_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("boards.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
