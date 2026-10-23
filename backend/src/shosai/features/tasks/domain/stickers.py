"""Custom stickers and their values (TK-D12, KG-D4; tasks plan §3.8, §3.15).

A custom sticker is a set of states, a number or a text, named in 1 to 40 characters; a set
holds at most 20 states, each named in 1 to 40 characters with a colour of the palette. An
owner holds 100 stickers, a board shows 20 of its own. A value is a state of that very
sticker, a number below 10¹² in size with at most two decimals, or a text of 1 to 200
characters, trimmed — and only of the sticker's own kind.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.features.tasks.domain.board_fields import Color

NAME_MAX: Final = 40
STATES_MAX: Final = 20
BOARD_STICKERS_MAX: Final = 20
STICKERS_MAX: Final = 100
TEXT_MAX: Final = 200
NUMBER_LIMIT: Final = Decimal(10) ** 12
CENT: Final = Decimal("0.01")


class StickerKind(StrEnum):
    """What a custom sticker holds."""

    STATES = "states"
    NUMBER = "number"
    TEXT = "text"


class StickerRule(StrEnum):
    """A rule of stickers; the value is the API's error code."""

    NAME_REQUIRED = "name_required"
    NAME_TOO_LONG = "name_too_long"
    STATES_FULL = "states_full"
    STICKERS_FULL = "stickers_full"
    BOARD_STICKERS_FULL = "board_stickers_full"
    KIND_MISMATCH = "value_kind_mismatch"
    INVALID = "validation_error"


class StickerRuleError(ValueError):
    """A sticker or a value breaks a rule."""

    def __init__(self, rule: StickerRule) -> None:
        super().__init__(rule.value)
        self.rule = rule
        self.code = rule.value


@dataclass(frozen=True, slots=True)
class StateDraft:
    """A state as a change sends it: kept by its id, new without one."""

    name: str
    color: Color
    state_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class StickerValue:
    """A task's value of a sticker: exactly one of a state, a number or a text."""

    state_id: UUID | None = None
    number: Decimal | None = None
    text: str | None = None

    @property
    def kind(self) -> StickerKind:
        """The kind of sticker that takes this value."""
        if self.state_id is not None:
            return StickerKind.STATES
        return StickerKind.NUMBER if self.number is not None else StickerKind.TEXT


def checked_name(raw: str) -> str:
    """A sticker's or a state's trimmed name, 1 to 40 characters."""
    name = raw.strip()
    if not name:
        raise StickerRuleError(StickerRule.NAME_REQUIRED)
    if len(name) > NAME_MAX:
        raise StickerRuleError(StickerRule.NAME_TOO_LONG)
    return name


def checked_states(states: list[StateDraft]) -> list[StateDraft]:
    """A set's states with their names checked; 20 at most."""
    if len(states) > STATES_MAX:
        raise StickerRuleError(StickerRule.STATES_FULL)
    return [StateDraft(checked_name(s.name), s.color, s.state_id) for s in states]


def checked_value(value: StickerValue, kind: StickerKind) -> StickerValue:
    """The value, if it is of the sticker's kind and within its bounds."""
    if value.kind is not kind:
        raise StickerRuleError(StickerRule.KIND_MISMATCH)
    if value.number is not None:
        return StickerValue(number=checked_number(value.number))
    if value.text is not None:
        text = value.text.strip()
        if not 0 < len(text) <= TEXT_MAX:
            raise StickerRuleError(StickerRule.INVALID)
        return StickerValue(text=text)
    return value


def checked_number(number: Decimal) -> Decimal:
    """A number below 10¹² in size with at most two decimals."""
    try:
        exact = number.quantize(CENT) == number
    except InvalidOperation as error:
        raise StickerRuleError(StickerRule.INVALID) from error
    if not number.is_finite() or abs(number) >= NUMBER_LIMIT or not exact:
        raise StickerRuleError(StickerRule.INVALID)
    return number
