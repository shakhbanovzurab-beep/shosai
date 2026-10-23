"""A person's boards as reads show them: summaries, columns with their cards, a whole board."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from shosai.features.tasks.application.sticker_views import BoardStickerView
from shosai.features.tasks.application.task_parts import CardRecord, Counts
from shosai.features.tasks.application.views import CardView
from shosai.features.tasks.domain.board_fields import Color
from shosai.features.tasks.domain.boards import BoardIcon
from shosai.features.tasks.domain.stickers import StickerValue
from shosai.features.tasks.domain.tasks import TaskStatus
from shosai.features.tasks.infrastructure.board_records import BoardColumnRecord


@dataclass(frozen=True, slots=True)
class BoardSummaryView:
    """A board in the person's list."""

    id: UUID
    name: str
    icon: BoardIcon
    incoming: bool
    task_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ColumnView:
    """A column with its cards in order."""

    id: UUID
    title: str
    kind: TaskStatus
    color: Color | None
    collapsed: bool
    cards: tuple[CardView, ...] = ()


@dataclass(frozen=True, slots=True)
class BoardDetailView:
    """A board as its screen shows it."""

    board: BoardSummaryView
    columns: tuple[ColumnView, ...]
    revision: int
    now: datetime
    stickers: tuple[BoardStickerView, ...] = ()


@dataclass(frozen=True, slots=True)
class BoardsView:
    """The person's boards and the incoming work that waits for a board."""

    items: tuple[BoardSummaryView, ...]
    incoming_board_id: UUID | None
    open_incoming: int


@dataclass(frozen=True, slots=True)
class PlacedCard:
    """A card of a board as its read finds it: the task, its column, counts and cover."""

    task: CardRecord
    column_id: UUID
    counted: tuple[Counts, UUID | None]
    values: Mapping[UUID, StickerValue] = field(default_factory=dict)


def column_of(record: BoardColumnRecord, cards: Sequence[CardView] = ()) -> ColumnView:
    """A column's view."""
    color = Color(record.color) if record.color else None
    kind = TaskStatus(record.kind)
    return ColumnView(record.id, record.title, kind, color, record.collapsed, tuple(cards))
