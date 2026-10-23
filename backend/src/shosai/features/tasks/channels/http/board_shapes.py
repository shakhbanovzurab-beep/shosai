"""Boards' views as the contract's shapes, and the contract's bodies as boards' requests."""

from datetime import UTC, datetime

from shosai.features.tasks.application.board_views import (
    BoardDetailView,
    BoardSummaryView,
    BoardsView,
    ColumnView,
)
from shosai.features.tasks.channels.http.board_models import (
    BoardDetailOut,
    BoardsOut,
    BoardSummaryOut,
    ColumnHeadOut,
    ColumnOut,
    IncomingOut,
    LayoutBody,
)
from shosai.features.tasks.channels.http.shapes import card_view_out
from shosai.features.tasks.channels.http.sticker_shapes import board_stickers_out
from shosai.features.tasks.domain.boards import LayoutColumn


def summary_out(view: BoardSummaryView) -> BoardSummaryOut:
    """A board's summary."""
    return BoardSummaryOut(
        id=view.id, name=view.name, icon=view.icon, jira=None, incoming=view.incoming,
        task_count=view.task_count, created_at=view.created_at,
    )  # fmt: skip


def boards_out(view: BoardsView) -> BoardsOut:
    """The person's boards and their incoming work."""
    return BoardsOut(
        items=[summary_out(item) for item in view.items],
        incoming=IncomingOut(board_id=view.incoming_board_id, open=view.open_incoming),
    )


def head_out(view: ColumnView) -> ColumnHeadOut:
    """A column without its cards."""
    return ColumnHeadOut(
        id=view.id, title=view.title, kind=view.kind, color=view.color, collapsed=view.collapsed
    )


def board_out(view: BoardDetailView) -> BoardDetailOut:
    """A board with its columns and cards."""
    columns = [
        ColumnOut(
            **head_out(column).model_dump(), cards=[card_view_out(card) for card in column.cards]
        )
        for column in view.columns
    ]
    return BoardDetailOut(
        board=summary_out(view.board), stickers=board_stickers_out(view.stickers), columns=columns,
        revision=view.revision, server_now=datetime.now(UTC),
    )  # fmt: skip


def layout_of(body: LayoutBody) -> tuple[LayoutColumn, ...]:
    """The layout a body asks for."""
    return tuple(
        LayoutColumn(column.id, column.title, tuple(column.task_ids)) for column in body.columns
    )
