"""The roles a model and a prompt serve, and what each needs (studio plan §3.2, ADR 0074).

`leo` is Leo's own role: its model is chosen in Settings > Leo and it takes no Studio prompt.
The five other roles are the ones a person sets in Studio. `transcript` is not a role: live
and recorded transcription are the platform's choice (ST-D2). The personal context goes to
every answer given to the person and never to the notes, which colleagues read.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class ModelCapability(StrEnum):
    """What a model can read: text, and pictures besides text."""

    TEXT = "text"
    VISION = "vision"


class Tier(StrEnum):
    """The class a model's tokens are counted in; billing's `ModelTier` by value."""

    STANDARD = "standard"
    FRONTIER = "frontier"


class ModelRole(StrEnum):
    """A role that runs on a model: Leo's and the five a person sets in Studio."""

    LEO = "leo"
    LIVE_ANSWERS = "live_answers"
    SCREENSHOTS = "screenshots"
    CODE = "code"
    SYSTEM_DESIGN = "system_design"
    NOTES = "notes"


class PromptRole(StrEnum):
    """A role that takes a person's prompt: every model role but Leo's."""

    LIVE_ANSWERS = "live_answers"
    SCREENSHOTS = "screenshots"
    CODE = "code"
    SYSTEM_DESIGN = "system_design"
    NOTES = "notes"


def model_role_of(role: PromptRole) -> ModelRole:
    """The model role of a prompt role: the same name."""
    return ModelRole(role.value)


TEXT: Final = frozenset({ModelCapability.TEXT})
TEXT_AND_VISION: Final = frozenset({ModelCapability.TEXT, ModelCapability.VISION})
# Что должна уметь любая модель роли — выбранная человеком или по умолчанию.
REQUIRED: Final[Mapping[ModelRole, frozenset[ModelCapability]]] = MappingProxyType(
    {role: TEXT_AND_VISION if role is ModelRole.SCREENSHOTS else TEXT for role in ModelRole}
)
# Модель Leo по умолчанию читает и картинки: ход с картинкой не остаётся без модели.
DEFAULT_REQUIRED: Final[Mapping[ModelRole, frozenset[ModelCapability]]] = MappingProxyType(
    {**REQUIRED, ModelRole.LEO: TEXT_AND_VISION}
)
# Заметки пишутся в фоне: их стандартные вызовы не считаются (F6-D6), лимит их не останавливает;
# frontier-выбор считается в неделю человека и уступает умолчанию, когда она кончилась (ST-D5).
BACKGROUND_ROLES: Final = frozenset({ModelRole.NOTES})
# Ответы человеку берут его контекст; записи встреч читают коллеги — им контекст не идёт.
CONTEXT_ROLES: Final = frozenset(ModelRole) - {ModelRole.NOTES}

TEMPERATURE_MIN: Final = Decimal(0)
TEMPERATURE_MAX: Final = Decimal(2)
MAX_TOKENS_MIN: Final = 256
MAX_TOKENS_CAP: Final = 32_768


@dataclass(frozen=True, slots=True)
class RoleSettings:
    """A person's model and its settings in one Studio role; no model means the default."""

    model_id: str | None
    temperature: Decimal
    max_tokens: int
    reasoning: bool


DEFAULT_TEMPERATURE: Final = Decimal("0.7")
DEFAULT_MAX_TOKENS: Final = 4_096
NOTES_MAX_TOKENS: Final = 8_192


def default_settings(role: PromptRole) -> RoleSettings:
    """The settings of a role the person never changed: reasoning off (draft `1c581580d`)."""
    tokens = NOTES_MAX_TOKENS if role is PromptRole.NOTES else DEFAULT_MAX_TOKENS
    return RoleSettings(None, DEFAULT_TEMPERATURE, tokens, reasoning=False)


# Настройки вызова Leo — agent'а (ST-D1): маршрут отдаёт умолчания, рассуждение решает agent.
LEO_SETTINGS: Final = RoleSettings(None, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS, reasoning=False)
