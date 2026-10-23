"""A board's columns and cards (`/v1/boards/{id}/columns*`, `/cards*`; tasks plan §3.14).

Columns are added, changed and removed with their cards moved; cards are put, copied,
moved and edited, a move setting the task's status by the column's kind. Errors use the
platform's envelope with the codes the cabinet words: `board_not_found`,
`column_not_found`, `task_not_found`, `title_required`, `title_too_long`,
`board_columns_full`, `board_full`, `last_column_of_kind`, `workspace_task_copy`,
`validation_error`.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.tasks.application.cards import CardChange, Cards, NewCard
from shosai.features.tasks.application.columns import ColumnChange, Columns, NewColumn
from shosai.features.tasks.channels.http.board_models import (
    CardCreateBody,
    CardPatchBody,
    ColumnCreateBody,
    ColumnHeadOut,
    ColumnPatchBody,
)
from shosai.features.tasks.channels.http.board_shapes import head_out
from shosai.features.tasks.channels.http.card_models import Card
from shosai.features.tasks.channels.http.shapes import card_out, invalid

NOT_NULL = frozenset({"title", "collapsed", "position", "column_id"})


def _refuse_nulls(sent: set[str], values: dict[str, object]) -> None:
    """A field the contract never clears is refused when sent as `null`."""
    if any(name in NOT_NULL and values.get(name) is None for name in sent):
        raise invalid()


def card_change_of(body: CardPatchBody) -> CardChange:
    """The change a card's body asks for; a move sends both its column and its position."""
    sent = body.model_fields_set
    _refuse_nulls(sent, body.model_dump())
    if ("column_id" in sent) != ("position" in sent):
        raise invalid()
    move = None
    if body.column_id is not None and body.position is not None:
        move = (body.column_id, body.position)
    return CardChange(
        title=body.title, priority=body.priority, priority_sent="priority" in sent, move=move
    )


def build_board_parts_router(services: tuple[Columns, Cards], ports: PortDirectory) -> APIRouter:
    """The routes of boards' columns and cards."""
    columns, cards = services
    router = APIRouter(prefix="/v1/boards/{board_id}", tags=["boards"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.post("/columns", status_code=HTTPStatus.CREATED)
    async def create_column(
        principal: person, board_id: UUID, body: ColumnCreateBody
    ) -> ColumnHeadOut:
        """Add a column at its position; 20 at most."""
        new = NewColumn(body.title, body.kind, body.position, body.color)
        return head_out(await columns.create(principal, board_id, new))

    @router.patch("/columns/{column_id}")
    async def change_column(
        principal: person, board_id: UUID, column_id: UUID, body: ColumnPatchBody
    ) -> ColumnHeadOut:
        """Rename, recolour, collapse or move a column."""
        sent = body.model_fields_set
        _refuse_nulls(sent, body.model_dump())
        change = ColumnChange(
            title=body.title, color=body.color, color_sent="color" in sent,
            collapsed=body.collapsed, position=body.position,
        )  # fmt: skip
        return head_out(await columns.change(principal, board_id, column_id, change))

    @router.delete("/columns/{column_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_column(principal: person, board_id: UUID, column_id: UUID) -> Response:
        """Remove a column; its cards go to the next column of its kind."""
        await columns.delete(principal, board_id, column_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post("/cards", status_code=HTTPStatus.CREATED)
    async def create_card(principal: person, board_id: UUID, body: CardCreateBody) -> Card:
        """Put a new card, or a copy of one, where it is asked."""
        new = NewCard(body.title, body.column_id, body.position, body.copy_of)
        return card_out(await cards.create(principal, board_id, new))

    @router.patch("/cards/{task_id}")
    async def change_card(
        principal: person, board_id: UUID, task_id: UUID, body: CardPatchBody
    ) -> Card:
        """Move or edit a card; another kind of column sets the task's status."""
        return card_out(await cards.change(principal, board_id, task_id, card_change_of(body)))

    return router
