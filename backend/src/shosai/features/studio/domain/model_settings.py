"""A person's model settings in a Studio role: checked when saved, applied per call.

The cabinet saves the model, temperature, output limit and reasoning together. A model must
be one the person's plan offers and able to serve the role; the output limit lies between
256 and the model's own limit, capped at 32 768. Reasoning is stored off for a model that
cannot reason, and a temperature is ignored by a model that takes none. No model means the
role's default; its limits are known only per call, so they are applied then.
"""

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Final

from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.roles import (
    MAX_TOKENS_CAP,
    MAX_TOKENS_MIN,
    REQUIRED,
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
    PromptRole,
    RoleSettings,
    Tier,
    model_role_of,
)

TEMPERATURE_STEP: Final = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class CallSettings:
    """What one call is asked with."""

    temperature: float | None
    max_tokens: int
    reasoning: bool


def offered(model: CatalogueModel | None, *, frontier_on_plan: bool) -> CatalogueModel | None:
    """The model when the person's plan offers it: usable, and frontier only with the plan."""
    if model is None or not model.usable:
        return None
    if model.tier is Tier.FRONTIER and not frontier_on_plan:
        return None
    return model


def checked_settings(
    role: PromptRole,
    settings: RoleSettings,
    model: CatalogueModel | None,
    *,
    frontier_on_plan: bool,
) -> RoleSettings:
    """The settings as they are stored; `model` is the catalogue's entry of `model_id`."""
    if not TEMPERATURE_MIN <= settings.temperature <= TEMPERATURE_MAX:
        message = "температура вне 0…2 доходит сюда только мимо схемы"
        raise ValueError(message)
    temperature = settings.temperature.quantize(TEMPERATURE_STEP, ROUND_HALF_EVEN)
    if settings.model_id is None:
        check_max_tokens(settings.max_tokens)
        return replace(settings, temperature=temperature)
    chosen = offered(model, frontier_on_plan=frontier_on_plan)
    if chosen is None:
        raise StudioRuleError(StudioRule.MODEL_NOT_ON_PLAN)
    if not chosen.can(REQUIRED[model_role_of(role)]):
        raise StudioRuleError(
            StudioRule.MODEL_CANT_DO_ROLE, {"model": chosen.name, "role": role.value}
        )
    if not MAX_TOKENS_MIN <= settings.max_tokens <= chosen.output_limit:
        raise StudioRuleError(
            StudioRule.MAX_TOKENS_RANGE, {"min": MAX_TOKENS_MIN, "max": chosen.output_limit}
        )
    reasoning = settings.reasoning and chosen.supports_reasoning
    return replace(settings, temperature=temperature, reasoning=reasoning)


def check_max_tokens(max_tokens: int) -> None:
    """Refuse an output limit outside what any model may be asked."""
    if not MAX_TOKENS_MIN <= max_tokens <= MAX_TOKENS_CAP:
        raise StudioRuleError(
            StudioRule.MAX_TOKENS_RANGE, {"min": MAX_TOKENS_MIN, "max": MAX_TOKENS_CAP}
        )


def call_settings(model: CatalogueModel, settings: RoleSettings) -> CallSettings:
    """What a call to this model is asked with, from the person's settings of the role."""
    temperature = float(settings.temperature) if model.supports_temperature else None
    max_tokens = min(max(settings.max_tokens, MAX_TOKENS_MIN), model.output_limit)
    return CallSettings(temperature, max_tokens, settings.reasoning and model.supports_reasoning)
