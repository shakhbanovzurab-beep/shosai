"""The shapes of boards the cabinet reads and sends (`domain/boards-contract.ts`; §3.14).

A board's summary, its columns with their cards, and until step 4s its system stickers
only, each with the board's visibility; the stopwatch carries its automations (ADR 0061).
The Jira link of a board is null until steps 12 and 13 connect Jira.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from shosai.features.tasks.channels.http.card_models import Card
from shosai.features.tasks.channels.http.detail_models import CustomStickerOut, StickerStateOut
from shosai.features.tasks.channels.http.out import Out
from shosai.features.tasks.channels.http.strict import Strict
from shosai.features.tasks.domain.board_fields import Color, SystemSticker
from shosai.features.tasks.domain.boards import BoardIcon, BoardTemplate
from shosai.features.tasks.domain.tasks import Priority, TaskStatus


class JiraLinkOut(Out):
    """Where a synced board comes from in Jira, and how its sync goes."""

    site: str
    project_key: str
    board_id: int
    board_name: str
    board_url: str
    sync_status: Literal["syncing", "synced", "error"]
    sync_error: str | None
    last_synced_at: datetime | None


class BoardSummaryOut(Out):
    """A board in the person's list."""

    id: UUID
    name: str
    icon: BoardIcon
    jira: JiraLinkOut | None = None
    incoming: bool
    task_count: int
    created_at: datetime


class IncomingOut(Out):
    """The board incoming work lands on, and how much waits while there is none."""

    board_id: UUID | None
    open: int


class BoardsOut(Out):
    """The person's boards."""

    items: list[BoardSummaryOut]
    incoming: IncomingOut


class ColumnHeadOut(Out):
    """A column of a board."""

    id: UUID
    title: str
    kind: TaskStatus
    color: Color | None
    collapsed: bool


class ColumnOut(ColumnHeadOut):
    """A column with its cards in order."""

    cards: list[Card]


class AutomationsOut(Out):
    """What the stopwatch does by itself on the board."""

    start_on_arrival: bool
    restart_on_move: bool
    stop_on_done: bool


class SystemStickerOut(Out):
    """A system field of the board and whether its cards show it."""

    id: SystemSticker
    kind: SystemSticker
    # Всегда null: у системного поля нет своего имени; тип не «null», а строка или null, потому что
    # openapi-fetch выбрасывает из ответа свойства, чей тип — один null.
    name: str | None = None
    states: list[StickerStateOut] = Field(default_factory=list)
    visible: bool


class StopwatchStickerOut(SystemStickerOut):
    """The stopwatch field, with its automations."""

    automations: AutomationsOut


class CustomBoardStickerOut(CustomStickerOut):
    """A custom sticker on a board and whether its cards show it."""

    visible: bool


class StickerBoardOut(Out):
    """A board a sticker is on."""

    id: UUID
    name: str


class StickerUsageOut(Out):
    """How many tasks carry a value of a sticker, in all and per state."""

    tasks: int
    states: dict[str, int]


class OwnedStickerOut(CustomStickerOut):
    """A sticker of its owner, with the boards it is on and its usage."""

    boards: list[StickerBoardOut]
    usage: StickerUsageOut


class StickersOut(Out):
    """The person's stickers."""

    items: list[OwnedStickerOut]


class BoardDetailOut(Out):
    """A board as its screen shows it."""

    board: BoardSummaryOut
    stickers: list[StopwatchStickerOut | SystemStickerOut | CustomBoardStickerOut]
    columns: list[ColumnOut]
    revision: int
    server_now: datetime


class BoardCreateBody(Strict):
    """A new board from a template."""

    name: str
    icon: BoardIcon
    template: BoardTemplate


class BoardPatchBody(Strict):
    """A board renamed or with another icon."""

    name: str | None = None
    icon: BoardIcon | None = None


class IncomingBody(Strict):
    """The board incoming work lands on, or none."""

    board_id: UUID | None


class LayoutColumnBody(Strict):
    """A column of the new layout with its cards in order."""

    id: UUID
    title: str
    task_ids: list[UUID]


class LayoutBody(Strict):
    """The whole layout of a board."""

    columns: Annotated[list[LayoutColumnBody], Field(max_length=20)]


class ColumnCreateBody(Strict):
    """A new column."""

    title: str
    kind: TaskStatus
    position: Annotated[int, Field(ge=0)]
    color: Color | None = None


class ColumnPatchBody(Strict):
    """A column's change; `color: null` removes the colour."""

    title: str | None = None
    color: Color | None = None
    collapsed: bool | None = None
    position: Annotated[int | None, Field(ge=0)] = None


class CardCreateBody(Strict):
    """A new card, or a copy of a card of the board."""

    title: str
    column_id: UUID
    position: Annotated[int, Field(ge=0)]
    copy_of: UUID | None = None


class CardPatchBody(Strict):
    """A card's change; a move sends the column and the position together."""

    title: str | None = None
    priority: Priority | None = None
    column_id: UUID | None = None
    position: Annotated[int | None, Field(ge=0)] = None


class JiraBoardOut(Out):
    """A Jira board the person's connection sees."""

    site: str
    board_id: int
    name: str
    project_key: str
    project_name: str
    type: Literal["kanban", "scrum"]
    synced_board_id: UUID | None


class JiraAvailableOut(Out):
    """The Jira boards the person's connection sees; none without a connection."""

    connected: bool
    account: str | None
    items: list[JiraBoardOut]


class JiraConnectBody(Strict):
    """A Jira board to sync."""

    site: Annotated[str, Field(min_length=1, max_length=200)]
    board_id: Annotated[int, Field(gt=0)]
