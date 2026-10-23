"""Stickers and values as the contract's shapes (`domain/stickers-contract.ts`; §3.15)."""

from collections.abc import Mapping, Sequence
from uuid import UUID

from shosai.features.tasks.application.sticker_views import (
    BoardStickerView,
    OwnedStickerView,
    StickerView,
)
from shosai.features.tasks.channels.http.board_models import (
    AutomationsOut,
    CustomBoardStickerOut,
    OwnedStickerOut,
    StickerBoardOut,
    StickerUsageOut,
    StopwatchStickerOut,
    SystemStickerOut,
)
from shosai.features.tasks.channels.http.card_models import (
    NumberValue,
    StateValue,
    StickerValue,
    TextValue,
)
from shosai.features.tasks.channels.http.detail_models import (
    CustomStickerOut,
    OtherValueOut,
    PersonOwner,
    StickerColor,
    StickerStateOut,
    WorkspaceOwner,
)
from shosai.features.tasks.domain import stickers
from shosai.features.tasks.domain.board_fields import SystemSticker

type BoardStickerOut = StopwatchStickerOut | SystemStickerOut | CustomBoardStickerOut


def sticker_out(view: StickerView) -> CustomStickerOut:
    """A custom sticker."""
    owner: PersonOwner | WorkspaceOwner = (
        PersonOwner(user_id=view.owner_user_id)
        if view.owner_org_id is None
        else WorkspaceOwner(workspace_id=view.owner_org_id)
    )
    states = [
        StickerStateOut(id=s.id, name=s.name, color=StickerColor(s.color.value))
        for s in view.states
    ]
    return CustomStickerOut(
        id=view.id, kind=view.kind.value, name=view.name, states=states, owner=owner
    )


def board_sticker_out(view: BoardStickerView) -> BoardStickerOut:
    """A sticker on a board."""
    sticker = view.sticker
    if not isinstance(sticker, SystemSticker):
        return CustomBoardStickerOut(**sticker_out(sticker).model_dump(), visible=view.visible)
    if view.automations is not None:
        automations = AutomationsOut(
            start_on_arrival=view.automations.start_on_arrival,
            restart_on_move=view.automations.restart_on_move,
            stop_on_done=view.automations.stop_on_done,
        )
        return StopwatchStickerOut(
            id=sticker, kind=sticker, visible=view.visible, automations=automations
        )
    return SystemStickerOut(id=sticker, kind=sticker, visible=view.visible)


def board_stickers_out(views: Sequence[BoardStickerView]) -> list[BoardStickerOut]:
    """A board's stickers in their order."""
    return [board_sticker_out(view) for view in views]


def owned_out(view: OwnedStickerView) -> OwnedStickerOut:
    """A sticker of its owner with its boards and usage."""
    usage = StickerUsageOut(
        tasks=view.usage.tasks, states={str(k): v for k, v in view.usage.states.items()}
    )
    boards = [StickerBoardOut(id=board_id, name=name) for board_id, name in view.boards]
    return OwnedStickerOut(**sticker_out(view.sticker).model_dump(), boards=boards, usage=usage)


def value_out(value: stickers.StickerValue) -> StickerValue:
    """A value as the contract sends it."""
    if value.state_id is not None:
        return StateValue(state_id=str(value.state_id))
    if value.number is not None:
        return NumberValue(number=float(value.number))
    return TextValue(text=value.text or "")


def values_out(values: Mapping[UUID, stickers.StickerValue]) -> dict[str, StickerValue]:
    """A card's values by sticker."""
    return {str(sticker_id): value_out(value) for sticker_id, value in values.items()}


def other_values_out(
    others: Sequence[tuple[StickerView, stickers.StickerValue]],
) -> list[OtherValueOut]:
    """The panel's values of stickers that are not on the reader's board."""
    return [OtherValueOut(sticker=sticker_out(s), value=value_out(v)) for s, v in others]
