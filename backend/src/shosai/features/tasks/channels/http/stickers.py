"""Stickers and values (`/v1/stickers*`, `/v1/boards/{id}/stickers*`, `/v1/tasks/{id}/values*`;
tasks plan §3.15).

A person's own stickers with their boards and usage, changed and deleted; stickers placed
on a board, shown or hidden — the system ones too — and removed; a task's values set and
cleared. Errors use the platform's envelope with the codes the cabinet words:
`sticker_not_found`, `state_not_found`, `sticker_not_on_board`, `system_sticker`,
`board_not_found`, `task_not_found`, `name_required`, `name_too_long`, `states_full`,
`stickers_full`, `board_stickers_full`, `value_kind_mismatch`, `jira_unsupported`,
`validation_error`.
"""

from decimal import Decimal
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import Field

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.tasks.application.board_stickers import BoardStickers, NewSticker
from shosai.features.tasks.application.stickers import Stickers
from shosai.features.tasks.application.values import Values
from shosai.features.tasks.channels.http.board_models import StickersOut
from shosai.features.tasks.channels.http.card_models import StickerValue
from shosai.features.tasks.channels.http.detail_models import CustomStickerOut
from shosai.features.tasks.channels.http.shapes import invalid
from shosai.features.tasks.channels.http.sticker_shapes import (
    BoardStickerOut,
    board_sticker_out,
    owned_out,
    sticker_out,
    value_out,
)
from shosai.features.tasks.channels.http.strict import Strict
from shosai.features.tasks.domain import stickers as rules
from shosai.features.tasks.domain.board_fields import Color, StopwatchAutomations
from shosai.features.tasks.domain.stickers import StateDraft, StickerKind


class StateBody(Strict):
    """A state of the full list: kept by its id, new without one."""

    id: UUID | None = None
    name: str
    color: Color


class StickerPatchBody(Strict):
    """A sticker renamed, or its states as the full list."""

    name: str | None = None
    states: list[StateBody] | None = None


class PlaceExistingBody(Strict):
    """The person's sticker to place."""

    sticker_id: UUID


class PlaceNewBody(Strict):
    """A new sticker to make and place."""

    kind: StickerKind
    name: str
    states: list[StateBody] | None = None


class AutomationsBody(Strict):
    """What the stopwatch does by itself on the board."""

    start_on_arrival: bool
    restart_on_move: bool
    stop_on_done: bool


class BoardStickerPatchBody(Strict):
    """A sticker shown or hidden on the board's cards; the stopwatch's automations."""

    visible: bool | None = None
    automations: AutomationsBody | None = None


class StateValueBody(Strict):
    """A value: one of the sticker's states."""

    state_id: UUID


class NumberValueBody(Strict):
    """A value: a number."""

    number: Annotated[Decimal, Field(allow_inf_nan=False)]


class TextValueBody(Strict):
    """A value: a text."""

    text: str


def drafts(states: list[StateBody] | None) -> list[StateDraft] | None:
    """The states a body sends, as drafts."""
    return None if states is None else [StateDraft(s.name, s.color, s.id) for s in states]


def value_of(body: StateValueBody | NumberValueBody | TextValueBody) -> rules.StickerValue:
    """The value a body sends."""
    if isinstance(body, StateValueBody):
        return rules.StickerValue(state_id=body.state_id)
    if isinstance(body, NumberValueBody):
        return rules.StickerValue(number=body.number)
    return rules.StickerValue(text=body.text)


def build_stickers_router(
    services: tuple[Stickers, BoardStickers], ports: PortDirectory
) -> APIRouter:
    """The routes of stickers and their places on boards."""
    stickers, placed = services
    router = APIRouter(tags=["stickers"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.get("/v1/stickers")
    async def list_stickers(principal: person) -> StickersOut:
        """The person's own stickers with their boards and usage."""
        return StickersOut(items=[owned_out(view) for view in await stickers.owned(principal)])

    @router.patch("/v1/stickers/{sticker_id}")
    async def change_sticker(
        principal: person, sticker_id: UUID, body: StickerPatchBody
    ) -> CustomStickerOut:
        """Rename a sticker or give its states as the full list."""
        if any(getattr(body, name) is None for name in body.model_fields_set):
            raise invalid()
        change = (body.name, drafts(body.states))
        return sticker_out(await stickers.change(principal, sticker_id, change))

    @router.delete("/v1/stickers/{sticker_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_sticker(principal: person, sticker_id: UUID) -> Response:
        """Delete a sticker: off every board, its values gone."""
        await stickers.delete(principal, sticker_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post("/v1/boards/{board_id}/stickers", status_code=HTTPStatus.CREATED)
    async def place_sticker(
        principal: person, board_id: UUID, body: PlaceExistingBody | PlaceNewBody
    ) -> BoardStickerOut:
        """Place one of the person's stickers, or a new one, on the board."""
        what: UUID | NewSticker = (
            body.sticker_id
            if isinstance(body, PlaceExistingBody)
            else NewSticker(body.kind, body.name, tuple(drafts(body.states) or ()))
        )
        return board_sticker_out(await placed.place(principal, board_id, what))

    @router.patch("/v1/boards/{board_id}/stickers/{sticker_id}")
    async def show_sticker(
        principal: person, board_id: UUID, sticker_id: str, body: BoardStickerPatchBody
    ) -> BoardStickerOut:
        """Show or hide a sticker on the board's cards; set the stopwatch's automations."""
        if body.visible is None and body.automations is None:
            raise invalid()
        automations = (
            None
            if body.automations is None
            else StopwatchAutomations(**body.automations.model_dump())
        )
        change = (sticker_id, body.visible, automations)
        return board_sticker_out(await placed.change(principal, board_id, change))

    @router.delete("/v1/boards/{board_id}/stickers/{sticker_id}", status_code=HTTPStatus.NO_CONTENT)
    async def remove_sticker(principal: person, board_id: UUID, sticker_id: str) -> Response:
        """Take a sticker off the board; the tasks keep their values."""
        await placed.remove(principal, board_id, sticker_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router


def build_values_router(values: Values, ports: PortDirectory) -> APIRouter:
    """The routes of tasks' values."""
    router = APIRouter(tags=["stickers"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.put("/v1/tasks/{task_id}/values/{sticker_id}")
    async def set_value(
        principal: person,
        task_id: UUID,
        sticker_id: UUID,
        body: StateValueBody | NumberValueBody | TextValueBody,
    ) -> StickerValue:
        """Set the task's value of a sticker."""
        return value_out(await values.put(principal, task_id, sticker_id, value_of(body)))

    @router.delete("/v1/tasks/{task_id}/values/{sticker_id}", status_code=HTTPStatus.NO_CONTENT)
    async def clear_value(principal: person, task_id: UUID, sticker_id: UUID) -> Response:
        """Clear the task's value of a sticker."""
        await values.clear(principal, task_id, sticker_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
