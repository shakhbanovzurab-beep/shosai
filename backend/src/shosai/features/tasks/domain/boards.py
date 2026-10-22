"""Boards and their columns (tasks plan §3.3, §3.4, TK-D5, the cabinet's `kanban/domain`).

A board belongs to one person. Its columns have a kind — to do, in progress, done — that is
the status of the cards they show, and every board keeps at least one column of each kind,
so a task of any status has a place. A new board's columns come from its template, named
by the server in the request's language. A layout reorders and renames what the board
shows; it never adds, drops or moves a card between columns, and a board that changed
meanwhile is refused (`board_changed`), as the cabinet's mocks answer.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.features.tasks.domain.tasks import TaskStatus

BOARDS_MAX: Final = 50
BOARD_COLUMNS_MAX: Final = 20
BOARD_OPEN_CARDS_MAX: Final = 1_000
BOARD_NAME_MAX: Final = 60
COLUMN_TITLE_MAX: Final = 60
# Закрытые раньше карточки уходят с доски и остаются в хранилище (TK-D5).
DONE_VISIBLE: Final = timedelta(days=30)

# Вид колонки — статус задач, которые она показывает.
type ColumnKind = TaskStatus


class BoardIcon(StrEnum):
    """The ten icons the cabinet offers for a board."""

    BRIEFCASE = "briefcase"
    HOME = "home"
    USER = "user"
    HEART = "heart"
    GRADUATION_CAP = "graduation-cap"
    PLANE = "plane"
    SHOPPING_CART = "shopping-cart"
    DUMBBELL = "dumbbell"
    ROCKET = "rocket"
    BOOK = "book"


class TemplateColumn(StrEnum):
    """A column a template brings; the server names it in the request's language."""

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class BoardTemplate(StrEnum):
    """How a new board starts."""

    SIMPLE = "simple"
    PROJECT = "project"


TEMPLATES: Final[dict[BoardTemplate, tuple[tuple[TemplateColumn, ColumnKind], ...]]] = {
    BoardTemplate.SIMPLE: (
        (TemplateColumn.TODO, TaskStatus.TODO),
        (TemplateColumn.IN_PROGRESS, TaskStatus.IN_PROGRESS),
        (TemplateColumn.DONE, TaskStatus.DONE),
    ),
    BoardTemplate.PROJECT: (
        (TemplateColumn.BACKLOG, TaskStatus.TODO),
        (TemplateColumn.TODO, TaskStatus.TODO),
        (TemplateColumn.IN_PROGRESS, TaskStatus.IN_PROGRESS),
        (TemplateColumn.REVIEW, TaskStatus.IN_PROGRESS),
        (TemplateColumn.DONE, TaskStatus.DONE),
    ),
}


class BoardRule(StrEnum):
    """A rule of boards; the value is the API's error code."""

    NAME_REQUIRED = "name_required"
    NAME_TOO_LONG = "name_too_long"
    TITLE_REQUIRED = "title_required"
    TITLE_TOO_LONG = "title_too_long"
    BOARDS_FULL = "boards_full"
    COLUMNS_FULL = "board_columns_full"
    BOARD_FULL = "board_full"
    LAST_COLUMN_OF_KIND = "last_column_of_kind"
    BOARD_CHANGED = "board_changed"


class BoardRuleError(ValueError):
    """A board breaks a rule."""

    def __init__(self, rule: BoardRule) -> None:
        super().__init__(rule.value)
        self.rule = rule
        self.code = rule.value


def checked_board_name(raw: str) -> str:
    """The trimmed name, 1 to 60 characters."""
    name = raw.strip()
    if not name:
        raise BoardRuleError(BoardRule.NAME_REQUIRED)
    if len(name) > BOARD_NAME_MAX:
        raise BoardRuleError(BoardRule.NAME_TOO_LONG)
    return name


def checked_column_title(raw: str) -> str:
    """The trimmed title of a column, 1 to 60 characters."""
    title = raw.strip()
    if not title:
        raise BoardRuleError(BoardRule.TITLE_REQUIRED)
    if len(title) > COLUMN_TITLE_MAX:
        raise BoardRuleError(BoardRule.TITLE_TOO_LONG)
    return title


def check_board_room(boards: int) -> None:
    """A person may hold 50 boards."""
    if boards >= BOARDS_MAX:
        raise BoardRuleError(BoardRule.BOARDS_FULL)


def check_column_room(columns: int) -> None:
    """A board may hold 20 columns."""
    if columns >= BOARD_COLUMNS_MAX:
        raise BoardRuleError(BoardRule.COLUMNS_FULL)


def check_card_room(open_cards: int, adding: int = 1) -> None:
    """A board may show 1 000 open cards (TK-D5)."""
    if open_cards + adding > BOARD_OPEN_CARDS_MAX:
        raise BoardRuleError(BoardRule.BOARD_FULL)


def check_kinds_kept(kinds: Sequence[ColumnKind]) -> None:
    """Every board keeps a column of each kind, so a task of any status has a place."""
    if set(TaskStatus) - set(kinds):
        raise BoardRuleError(BoardRule.LAST_COLUMN_OF_KIND)


@dataclass(frozen=True, slots=True)
class ShownColumn:
    """A column as the board shows it now: its id and the cards it shows, in order."""

    column_id: UUID
    card_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class LayoutColumn:
    """A column of a proposed layout: its title and its cards in the new order."""

    column_id: UUID
    title: str
    task_ids: tuple[UUID, ...]


def checked_layout(
    shown: Sequence[ShownColumn], layout: Sequence[LayoutColumn]
) -> tuple[LayoutColumn, ...]:
    """The layout with its titles checked, if it holds exactly the columns and cards shown.

    Each column must keep the very cards it shows, only reordered; cards the board no longer
    shows (done more than 30 days ago) are not the client's to order and stay after them.
    """
    current = {column.column_id: frozenset(column.card_ids) for column in shown}
    ids = [column.column_id for column in layout]
    if len(ids) != len(set(ids)) or set(ids) != set(current):
        raise BoardRuleError(BoardRule.BOARD_CHANGED)
    for column in layout:
        if len(column.task_ids) != len(set(column.task_ids)):
            raise BoardRuleError(BoardRule.BOARD_CHANGED)
        if frozenset(column.task_ids) != current[column.column_id]:
            raise BoardRuleError(BoardRule.BOARD_CHANGED)
    return tuple(
        LayoutColumn(column.column_id, checked_column_title(column.title), column.task_ids)
        for column in layout
    )
