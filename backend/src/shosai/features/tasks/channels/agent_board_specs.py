"""Leo's `boards` toolset as the model sees it: the person's Kanban boards and their columns.

A toolset of its own, since `tasks` holds its eight tools' worth of words (Leo §8.1). One read
lists the boards; seven writes make, change and delete a board, add, change and remove a
column, and choose the board incoming work lands on — each only after the person approves
its card. A task goes onto a board with `tasks.move`. The results carry ids and the person's
own names only, so they have no provenance label.
"""

from datetime import timedelta
from typing import Final
from uuid import UUID

from pydantic import BaseModel, Field

from shosai.core.agent_tools.previews import PreviewWording
from shosai.core.agent_tools.spec import Reversibility, ToolEffect, ToolSpec
from shosai.features.tasks.channels import agent_board_words as words
from shosai.features.tasks.channels.agent_tool_models import Strict
from shosai.features.tasks.domain.board_fields import Color
from shosai.features.tasks.domain.boards import (
    BOARD_COLUMNS_MAX,
    BOARD_NAME_MAX,
    COLUMN_TITLE_MAX,
    BoardIcon,
    BoardTemplate,
)
from shosai.features.tasks.domain.tasks import TaskStatus

TOOLSET: Final = "boards"
# Клиентский домен запросов кабинета, который перечитывается после записи.
BOARDS_DOMAIN: Final = ("tasks",)


class NoArguments(Strict):
    """Nothing to choose."""


class BoardLine(BaseModel):
    """One of the person's boards."""

    board_id: UUID
    name: str
    icon: BoardIcon
    incoming: bool = Field(description="Incoming tasks land on this board.")
    open_tasks: int


class BoardsListed(BaseModel):
    """The person's boards, oldest first."""

    boards: list[BoardLine]
    waiting_incoming: int = Field(description="Incoming tasks waiting for a board.")


class ColumnDraft(Strict):
    """A column of a new board."""

    title: str = Field(min_length=1, max_length=COLUMN_TITLE_MAX, description="Its title.")
    kind: TaskStatus = Field(description="todo, in_progress or done: the status it shows.")


class CreateBoard(Strict):
    """A new board: from a template, or with its own columns."""

    name: str = Field(min_length=1, max_length=BOARD_NAME_MAX, description="The board's name.")
    icon: BoardIcon = Field(default=BoardIcon.BRIEFCASE, description="One of the ten icons.")
    template: BoardTemplate = Field(
        default=BoardTemplate.SIMPLE,
        description="simple: to do, in progress, done; project: backlog, to do, in progress, "
        "review, done. Ignored when columns are given.",
    )
    columns: list[ColumnDraft] | None = Field(
        default=None, min_length=1, max_length=BOARD_COLUMNS_MAX,
        description="Columns in order, in the user's language; every kind at least once.",
    )  # fmt: skip


class BoardMade(BaseModel):
    """The board made."""

    board_id: UUID
    columns: list[UUID] = Field(description="Its columns' ids, left to right.")


class UpdateBoard(Strict):
    """A board renamed or given another icon."""

    board_id: UUID = Field(description="One of the user's boards.")
    name: str | None = Field(default=None, min_length=1, max_length=BOARD_NAME_MAX)
    icon: BoardIcon | None = None


class BoardRef(Strict):
    """One of the person's boards."""

    board_id: UUID = Field(description="One of the user's boards.")


class Done(BaseModel):
    """The change is made."""

    done: bool = True


class AddColumn(Strict):
    """A column added to a board."""

    board_id: UUID = Field(description="One of the user's boards.")
    title: str = Field(min_length=1, max_length=COLUMN_TITLE_MAX)
    kind: TaskStatus = Field(description="todo, in_progress or done: the status it shows.")
    position: int = Field(
        default=10_000, ge=0, le=10_000, description="0 is the first; the end by default."
    )
    color: Color | None = None


class ColumnMade(BaseModel):
    """The column made."""

    column_id: UUID


class UpdateColumn(Strict):
    """A column renamed, moved, recoloured or collapsed; only the fields given change."""

    board_id: UUID = Field(description="One of the user's boards.")
    column_id: UUID = Field(description="A column of that board.")
    title: str | None = Field(default=None, min_length=1, max_length=COLUMN_TITLE_MAX)
    position: int | None = Field(default=None, ge=0, le=10_000, description="0 is the first.")
    color: Color | None = Field(default=None, description="A colour; null removes it.")
    collapsed: bool | None = None


class ColumnRef(Strict):
    """A column of one of the person's boards."""

    board_id: UUID = Field(description="One of the user's boards.")
    column_id: UUID = Field(description="A column of that board.")


class ChooseIncoming(Strict):
    """The board incoming tasks land on, or none."""

    board_id: UUID | None = Field(description="One of the user's boards; null for none.")


def board_spec[I: BaseModel, O: BaseModel](
    name: str,
    description: str,
    models: tuple[type[I], type[O]],
    card: tuple[Reversibility, tuple[PreviewWording, ...]],
) -> ToolSpec[I, O]:
    """A write of the toolset, with how it can be undone and the words of its cards."""
    reversibility, previews = card
    return ToolSpec(
        name=f"{TOOLSET}.{name}", toolset=TOOLSET, description=description, input=models[0],
        output=models[1], effect=ToolEffect.WRITE, reversibility=reversibility,
        result_budget=600, timeout=timedelta(seconds=10), invalidates=BOARDS_DOMAIN,
        previews=previews,
    )  # fmt: skip


LIST: Final = ToolSpec(
    name=f"{TOOLSET}.list", toolset=TOOLSET,
    description="List the user's Kanban boards: name, icon, open tasks, and which one incoming"
    " tasks land on. Read a board's columns and cards with tasks.list_board.",
    input=NoArguments, output=BoardsListed, effect=ToolEffect.READ, result_budget=3_000,
    timeout=timedelta(seconds=5),
)  # fmt: skip
CREATE: Final = board_spec(
    "create",
    "Make a Kanban board for the user from a template, or with columns of their own. The user"
    " approves it first.",
    (CreateBoard, BoardMade),
    (Reversibility.COMPENSABLE, (words.CREATE,)),
)
UPDATE: Final = board_spec(
    "update",
    "Rename one of the user's boards or change its icon. The user approves it first.",
    (UpdateBoard, Done),
    (Reversibility.REVERSIBLE, (words.UPDATE,)),
)
DELETE: Final = board_spec(
    "delete",
    "Delete one of the user's boards. The personal tasks made on it go with it; tasks of"
    " meetings and workspaces stay. It cannot be undone. The user approves it first.",
    (BoardRef, Done),
    (Reversibility.IRREVERSIBLE, (words.DELETE,)),
)
ADD_COLUMN: Final = board_spec(
    "add_column",
    "Add a column to one of the user's boards. The user approves it first.",
    (AddColumn, ColumnMade),
    (Reversibility.REVERSIBLE, (words.ADD_COLUMN,)),
)
UPDATE_COLUMN: Final = board_spec(
    "update_column",
    "Rename, move, recolour or collapse a column of one of the user's boards. The user"
    " approves it first.",
    (UpdateColumn, Done),
    (Reversibility.REVERSIBLE, (words.UPDATE_COLUMN,)),
)
DELETE_COLUMN: Final = board_spec(
    "delete_column",
    "Remove a column of one of the user's boards; its cards go on top of the next column of"
    " the same kind, and the last column of a kind cannot go. The user approves it first.",
    (ColumnRef, Done),
    (Reversibility.COMPENSABLE, (words.DELETE_COLUMN,)),
)
CHOOSE_INCOMING: Final = board_spec(
    "set_incoming",
    "Choose the board new tasks that come to the user land on, or none. The user approves it"
    " first.",
    (ChooseIncoming, Done),
    (Reversibility.REVERSIBLE, (words.INCOMING, words.NO_INCOMING)),
)
BOARD_TOOLS: Final = (
    LIST, CREATE, UPDATE, DELETE, ADD_COLUMN, UPDATE_COLUMN, DELETE_COLUMN, CHOOSE_INCOMING,
)  # fmt: skip
