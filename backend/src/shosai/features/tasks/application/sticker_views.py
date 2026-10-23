"""Stickers and values as reads show them (tasks plan §3.8, §3.15).

A board's stickers are the system ones in their order, with the board's visibility and the
stopwatch's automations, then its own in the order placed. A board read keeps its round
trips: its own stickers come with the board's row and a card's values with the card's, as
JSON built in the statement. A task's panel reads its values with their stickers' definitions:
those on the reader's board show on the card, the rest as `other_values`.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import ScalarSelect, Text, and_, cast, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.tasks.domain.board_fields import (
    NEW_BOARD_VISIBILITY,
    Color,
    StopwatchAutomations,
    SystemSticker,
)
from shosai.features.tasks.domain.stickers import StickerKind, StickerValue
from shosai.features.tasks.infrastructure.sticker_records import (
    BoardStickerRecord,
    StickerRecord,
    StickerStateRecord,
    TaskStickerValueRecord,
)
from shosai.features.tasks.infrastructure.task_records import TaskRecord

PLACED: Final = BoardStickerRecord
VALUES: Final = TaskStickerValueRecord


@dataclass(frozen=True, slots=True)
class StateView:
    """A state of a set-of-states sticker."""

    id: UUID
    name: str
    color: Color


@dataclass(frozen=True, slots=True)
class StickerView:
    """A custom sticker: its kind, name, states and owner."""

    id: UUID
    kind: StickerKind
    name: str
    states: tuple[StateView, ...]
    owner_user_id: UUID
    owner_org_id: UUID | None


@dataclass(frozen=True, slots=True)
class BoardStickerView:
    """A sticker on a board, shown on its cards or not; the stopwatch with its automations."""

    sticker: SystemSticker | StickerView
    visible: bool
    automations: StopwatchAutomations | None = None


@dataclass(frozen=True, slots=True)
class UsageView:
    """How many tasks carry a value of a sticker, in all and per state."""

    tasks: int
    states: Mapping[UUID, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OwnedStickerView:
    """A sticker of its owner, with the boards it is on and its usage."""

    sticker: StickerView
    boards: tuple[tuple[UUID, str], ...]
    usage: UsageView


def system_stickers(
    visibility: Mapping[str, bool], automations: Mapping[str, bool]
) -> list[BoardStickerView]:
    """The board's system stickers in their order."""
    stopwatch = StopwatchAutomations(**{k: bool(v) for k, v in automations.items()})
    return [
        BoardStickerView(
            sticker,
            bool(visibility.get(sticker.value, NEW_BOARD_VISIBILITY[sticker])),
            stopwatch if sticker is SystemSticker.STOPWATCH else None,
        )
        for sticker in SystemSticker
    ]


def states_json() -> ScalarSelect[object]:
    """A sticker row's states in their order, as one JSON array."""
    state = func.json_build_object(
        "id", StickerStateRecord.id, "name", StickerStateRecord.name,
        "color", StickerStateRecord.color,
    )  # fmt: skip
    return (
        select(
            func.coalesce(
                func.json_agg(aggregate_order_by(state, StickerStateRecord.position)),
                func.json_build_array(),
            )
        )
        .where(StickerStateRecord.sticker_id == StickerRecord.id)
        .scalar_subquery()
    )


def board_stickers_json(board_id: object) -> ScalarSelect[object]:
    """The board's own stickers in their order with their states, as one JSON array."""
    sticker = func.json_build_object(
        "id", StickerRecord.id, "kind", StickerRecord.kind, "name", StickerRecord.name,
        "user_id", StickerRecord.user_id, "org_id", StickerRecord.org_id,
        "visible", PLACED.visible, "states", states_json(),
    )  # fmt: skip
    return (
        select(
            func.coalesce(
                func.json_agg(aggregate_order_by(sticker, PLACED.position)), func.json_build_array()
            )
        )
        .select_from(PLACED)
        .join(StickerRecord, StickerRecord.id == PLACED.sticker_id)
        .where(PLACED.board_id == board_id)
        .scalar_subquery()
    )


def card_values_json(board_id: object) -> ScalarSelect[object]:
    """A task row's values of the board's own stickers, as one JSON object by sticker."""
    value = func.json_build_object(
        "state_id", VALUES.state_id, "number", cast(VALUES.number, Text),
        "text", VALUES.text,
    )  # fmt: skip
    on_board = and_(PLACED.sticker_id == VALUES.sticker_id, PLACED.board_id == board_id)
    return (
        select(
            func.coalesce(func.json_object_agg(VALUES.sticker_id, value), func.json_build_object())
        )
        .select_from(VALUES)
        .join(PLACED, on_board)
        .where(VALUES.task_id == TaskRecord.id)
        .scalar_subquery()
    )


def stickers_of(raw: object) -> list[BoardStickerView]:
    """The board's own stickers from `board_stickers_json`."""
    return [BoardStickerView(sticker_of(item), bool(item["visible"])) for item in _items(raw)]


def sticker_of(item: Mapping[str, object]) -> StickerView:
    """A sticker from its JSON."""
    org = item.get("org_id")
    return StickerView(
        id=UUID(str(item["id"])),
        kind=StickerKind(str(item["kind"])),
        name=str(item["name"]),
        states=tuple(
            StateView(UUID(str(s["id"])), str(s["name"]), Color(str(s["color"])))
            for s in _items(item.get("states"))
        ),
        owner_user_id=UUID(str(item["user_id"])),
        owner_org_id=None if org is None else UUID(str(org)),
    )


def _items(raw: object) -> list[Mapping[str, object]]:
    """The objects of a JSON array, whether the driver parsed it or not."""
    found = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(found, list):
        return []
    return [item for item in found if isinstance(item, dict)]


def values_of(raw: object) -> dict[UUID, StickerValue]:
    """A card's values from `card_values_json`."""
    found = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(found, dict):
        return {}
    return {UUID(key): value_of(item) for key, item in found.items()}


def value_of(item: Mapping[str, object]) -> StickerValue:
    """A value from its JSON or its row's fields."""
    state, number, text = item.get("state_id"), item.get("number"), item.get("text")
    return StickerValue(
        state_id=None if state is None else UUID(str(state)),
        number=None if number is None else Decimal(str(number)),
        text=None if text is None else str(text),
    )


async def task_values(
    session: AsyncSession, task_id: UUID
) -> list[tuple[StickerView, StickerValue]]:
    """A task's values with their stickers' definitions."""
    rows = await session.execute(
        select(
            StickerRecord.id, StickerRecord.kind, StickerRecord.name, StickerRecord.user_id,
            StickerRecord.org_id, states_json(), VALUES.state_id, VALUES.number, VALUES.text,
        )
        .join(StickerRecord, StickerRecord.id == VALUES.sticker_id)
        .where(VALUES.task_id == task_id)
        .order_by(StickerRecord.created_at, StickerRecord.id)
    )  # fmt: skip
    found: list[tuple[StickerView, StickerValue]] = []
    for sticker_id, kind, name, owner, org, states, state, number, text in rows:
        item = {"id": sticker_id, "kind": kind, "name": name, "user_id": owner, "org_id": org}
        sticker = sticker_of({**item, "states": states})
        found.append((sticker, StickerValue(state_id=state, number=number, text=text)))
    return found


def split_values(
    values: Sequence[tuple[StickerView, StickerValue]], on_board: set[UUID]
) -> tuple[dict[UUID, StickerValue], tuple[tuple[StickerView, StickerValue], ...]]:
    """The values of the board's stickers, and the others with their stickers."""
    shown = {sticker.id: value for sticker, value in values if sticker.id in on_board}
    others = tuple((s, v) for s, v in values if s.id not in on_board)
    return shown, others
