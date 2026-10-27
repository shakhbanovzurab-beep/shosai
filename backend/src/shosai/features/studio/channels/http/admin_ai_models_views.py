"""The AI models screen's contract (`frontend/src/features/admin-ai-models/domain/contract.ts`).

Money is USD as JSON numbers; days are business dates (ADR 0058). Beyond the cabinet's first
contract: each model's tier, a pending tier proposal, what it reads and its output limit, the
defaults of every role, the month's requests and the spend outside the catalogue. The
connection check and a missing balance answer codes, worded by the cabinet.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from shosai.features.studio.application.ai_models_screen import (
    ConnectionCheck,
    KeyState,
    ModelRow,
    Screen,
    Spend,
)
from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.defaults import RoleDefault
from shosai.features.studio.domain.roles import ModelCapability, ModelRole, Tier


class AdminCredits(BaseModel):
    """OpenRouter's credits, USD."""

    total: float
    used: float
    remaining: float


class AdminProviderStatus(BaseModel):
    """The OpenRouter key and balance."""

    provider: Literal["openrouter"] = "openrouter"
    key_configured: bool
    key_hint: str | None
    credits: AdminCredits | None
    source: Literal["backend"] = "backend"
    sync_error: str | None = Field(description="An error code when the balance was not read.")


class AdminDailySpend(BaseModel):
    """One business day's spend."""

    date: date
    cost: float


class AdminOutsideCatalogue(BaseModel):
    """This month's spend on models outside the catalogue."""

    spend: float
    requests: int


class AdminSpendSummary(BaseModel):
    """The platform's AI spend this business month."""

    today: float
    month: float
    forecast_month: float
    tokens_in_month: int
    tokens_out_month: int
    requests_month: int
    outside_catalogue: AdminOutsideCatalogue
    daily: list[AdminDailySpend]


class AdminAiModel(BaseModel):
    """A model of the catalogue."""

    id: str
    openrouter_id: str
    name: str
    provider: str = Field(description="The model's maker.")
    context_length: int
    max_output_tokens: int
    capabilities: list[ModelCapability]
    price_input_per_m: float | None
    price_output_per_m: float | None
    month_spend: float
    month_requests: int
    enabled: bool
    is_default: bool = Field(description="Whether the model is Leo's default.")
    tier: Tier
    tier_proposed: Tier | None


class AdminRoleDefault(BaseModel):
    """A role's default and fallback."""

    role: ModelRole
    model_id: str
    fallback_model_id: str | None


class AdminAiModels(BaseModel):
    """The whole screen."""

    provider: AdminProviderStatus
    spend: AdminSpendSummary
    models: list[AdminAiModel]
    defaults: list[AdminRoleDefault]


class AdminConnectionCheck(BaseModel):
    """The connection check's answer."""

    ok: bool
    latency_ms: int | None
    code: str | None
    checked_at: datetime
    provider: AdminProviderStatus


class AdminAiModelAdd(BaseModel):
    """A model to list, by OpenRouter's id; the tier its price proposes unless given."""

    model_config = ConfigDict(extra="forbid")

    openrouter_id: str = Field(min_length=1, max_length=128)
    tier: Tier | None = None


class AdminAiModelSwitch(BaseModel):
    """Switch a model on or off."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool


class AdminRoleDefaultBody(BaseModel):
    """A role's new default and optional fallback."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1, max_length=64)
    fallback_model_id: str | None = Field(default=None, min_length=1, max_length=64)


class AdminTierDecision(BaseModel):
    """The admin's answer to a tier the price proposes."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["confirm", "decline"]


def provider_of(state: KeyState) -> AdminProviderStatus:
    """The contract's provider status."""
    credits = state.credits
    return AdminProviderStatus(
        key_configured=state.configured,
        key_hint=state.hint,
        credits=None
        if credits is None
        else AdminCredits(
            total=float(credits.total_usd),
            used=float(credits.used_usd),
            remaining=float(credits.left_usd),
        ),
        sync_error=state.sync_error,
    )


def spend_of(spend: Spend) -> AdminSpendSummary:
    """The contract's spend summary."""
    return AdminSpendSummary(
        today=float(spend.today),
        month=float(spend.month),
        forecast_month=float(spend.forecast_month),
        tokens_in_month=spend.tokens_in_month,
        tokens_out_month=spend.tokens_out_month,
        requests_month=spend.requests_month,
        outside_catalogue=AdminOutsideCatalogue(
            spend=float(spend.outside_spend), requests=spend.outside_requests
        ),
        daily=[AdminDailySpend(date=day, cost=float(cost)) for day, cost in spend.daily],
    )


def model_of(row: ModelRow, leo_default: str | None) -> AdminAiModel:
    """The contract's model of a row."""
    model: CatalogueModel = row.model
    return AdminAiModel(
        id=model.id,
        openrouter_id=model.openrouter_id,
        name=model.name,
        provider=model.maker,
        context_length=model.context_length,
        max_output_tokens=model.output_limit,
        capabilities=sorted(model.capabilities),
        price_input_per_m=None if row.price_input_per_m is None else float(row.price_input_per_m),
        price_output_per_m=None
        if row.price_output_per_m is None
        else float(row.price_output_per_m),
        month_spend=float(row.month_spend),
        month_requests=row.month_requests,
        enabled=model.enabled,
        is_default=model.id == leo_default,
        tier=model.tier,
        tier_proposed=model.tier_proposed,
    )


def default_view(default: RoleDefault) -> AdminRoleDefault:
    """The contract's view of a role's defaults."""
    return AdminRoleDefault(
        role=default.role, model_id=default.model_id, fallback_model_id=default.fallback_id
    )


def leo_default_of(defaults: tuple[RoleDefault, ...]) -> str | None:
    """Leo's default model, if one is set."""
    return next((item.model_id for item in defaults if item.role is ModelRole.LEO), None)


def screen_of(screen: Screen) -> AdminAiModels:
    """The contract's whole screen."""
    leo = leo_default_of(screen.defaults)
    return AdminAiModels(
        provider=provider_of(screen.provider),
        spend=spend_of(screen.spend),
        models=[model_of(row, leo) for row in screen.models],
        defaults=[default_view(item) for item in screen.defaults],
    )


def check_of(check: ConnectionCheck) -> AdminConnectionCheck:
    """The contract's connection check."""
    return AdminConnectionCheck(
        ok=check.ok,
        latency_ms=check.latency_ms,
        code=check.code,
        checked_at=check.checked_at,
        provider=provider_of(check.provider),
    )
