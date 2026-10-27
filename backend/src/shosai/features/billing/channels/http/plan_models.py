"""The admin's plan in the cabinet's contract (`admin-plans/domain/contract.ts`), and back.

Beyond the cabinet's fields a plan carries weekly tokens per model tier, the standard
model's daily tokens (BL-D4) and the `frontier_models` capability; they are optional in
a request, so a form that does not know them keeps working. A PATCH merges into the
current plan, nested limits and capabilities key by key, and the result is checked
whole, as the cabinet does.
"""

from datetime import datetime
from typing import Annotated, Any, Final
from uuid import UUID

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from shosai.features.billing.domain.money import MAX_MINOR, Currency, Prices
from shosai.features.billing.domain.plans import (
    FEATURE_MAX,
    FEATURES_MAX,
    NAME_MAX,
    SORT_MAX,
    Audience,
    BillingPeriod,
    Capability,
    ModelTier,
    Plan,
    PlanLimits,
    SeatRange,
)

SEATS_MAX: Final = 100_000
TOKENS_MAX: Final = 1_000_000_000_000
NESTED: Final = ("limits", "capabilities")

Minor = Annotated[int, Field(ge=0, le=MAX_MINOR)]
Seats = Annotated[int, Field(ge=1, le=SEATS_MAX)]
Tokens = Annotated[int, Field(ge=0, le=TOKENS_MAX)]
Feature = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=FEATURE_MAX)
]


class Strict(BaseModel):
    """A request part: unknown fields are refused."""

    model_config = ConfigDict(extra="forbid")


class PriceSet(Strict):
    """A period's price in minor units in every currency."""

    RUB: Minor
    USD: Minor
    EUR: Minor


class SeatsBody(Strict):
    """How many users a per-seat plan is for; no upper bound when `max` is null."""

    min: Seats
    max: Seats | None


class LimitsBody(Strict):
    """What a plan includes: null is unlimited, 0 is not included."""

    meeting_minutes_per_month: Annotated[int, Field(ge=0, le=1_000_000)] | None
    file_manager_gb: Annotated[int, Field(ge=0, le=1_000_000)] | None
    knowledge_base_mb: Annotated[int, Field(ge=0, le=100_000_000)] | None
    weekly_standard_tokens: Tokens | None = None
    weekly_frontier_tokens: Tokens | None = 0
    daily_standard_tokens: Tokens | None = None
    room_participants: Annotated[
        int | None,
        Field(
            ge=2,
            le=1_000,
            description="People in one video call; null takes the platform's ceiling (50).",
        ),
    ] = None


class CapabilitiesBody(Strict):
    """The extras a plan switches on."""

    shared_workspace: bool
    member_management: bool
    centralized_billing: bool
    sso: bool
    admin_controls: bool
    priority_support: bool
    usage_analytics: bool
    frontier_models: bool = False


class PlanDraftBody(Strict):
    """A plan as the admin's form sends it."""

    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)
    ]
    slug: Annotated[
        str, StringConstraints(min_length=2, max_length=40, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    ]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
    audience: Audience
    seats: SeatsBody | None
    custom_pricing: bool
    price_monthly: PriceSet
    price_yearly: PriceSet
    limits: LimitsBody
    capabilities: CapabilitiesBody
    features: Annotated[list[Feature], Field(max_length=FEATURES_MAX)]
    is_active: bool
    is_featured: bool
    sort_order: Annotated[int, Field(ge=0, le=SORT_MAX)]


class PlanPatchBody(Strict):
    """Any part of the draft; `archived: false` restores, `true` archives."""

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    audience: Audience | None = None
    seats: SeatsBody | None = None
    custom_pricing: bool | None = None
    price_monthly: PriceSet | None = None
    price_yearly: PriceSet | None = None
    limits: dict[str, int | None] | None = None
    capabilities: dict[str, bool] | None = None
    features: list[str] | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    sort_order: int | None = None
    archived: bool | None = None


class PlanView(PlanDraftBody):
    """A plan as the admin's list shows it."""

    id: UUID
    subscribers: int
    archived: bool
    created_at: datetime
    updated_at: datetime


def price_set(prices: Prices) -> PriceSet:
    """The contract's prices of a period."""
    return PriceSet(**{currency.value: amount for currency, amount in prices.amounts.items()})


def prices_of(prices: PriceSet) -> Prices:
    """The domain prices of a period."""
    return Prices({currency: getattr(prices, currency.value) for currency in Currency})


def draft_of(plan: Plan) -> PlanDraftBody:
    """The contract's draft of a domain plan."""
    limits = plan.limits
    seats = None if plan.seats is None else SeatsBody(min=plan.seats.min, max=plan.seats.max)
    return PlanDraftBody(
        name=plan.name, slug=plan.slug, description=plan.description, audience=plan.audience,
        seats=seats, custom_pricing=plan.custom_pricing,
        price_monthly=price_set(plan.prices[BillingPeriod.MONTH]),
        price_yearly=price_set(plan.prices[BillingPeriod.YEAR]),
        limits=LimitsBody(
            meeting_minutes_per_month=limits.meeting_minutes_per_month,
            file_manager_gb=limits.file_manager_gb, knowledge_base_mb=limits.knowledge_base_mb,
            weekly_standard_tokens=limits.weekly_tokens[ModelTier.STANDARD],
            weekly_frontier_tokens=limits.weekly_tokens[ModelTier.FRONTIER],
            daily_standard_tokens=limits.daily_standard_tokens,
            room_participants=limits.room_participants,
        ),
        capabilities=CapabilitiesBody(
            **{capability.value: capability in plan.capabilities for capability in Capability}
        ),
        features=list(plan.features), is_active=plan.on_sale, is_featured=plan.featured,
        sort_order=plan.sort_order,
    )  # fmt: skip


def plan_of(body: PlanDraftBody, *, archived: bool) -> Plan:
    """The domain plan of a draft; a broken catalogue rule raises its coded error."""
    limits = body.limits
    capabilities = body.capabilities.model_dump()
    return Plan(
        slug=body.slug, name=body.name, audience=body.audience,
        limits=PlanLimits(
            meeting_minutes_per_month=limits.meeting_minutes_per_month,
            file_manager_gb=limits.file_manager_gb, knowledge_base_mb=limits.knowledge_base_mb,
            weekly_tokens={
                ModelTier.STANDARD: limits.weekly_standard_tokens,
                ModelTier.FRONTIER: limits.weekly_frontier_tokens,
            },
            daily_standard_tokens=limits.daily_standard_tokens,
            room_participants=limits.room_participants,
        ),
        capabilities=frozenset(Capability(name) for name, on in capabilities.items() if on),
        prices={
            BillingPeriod.MONTH: prices_of(body.price_monthly),
            BillingPeriod.YEAR: prices_of(body.price_yearly),
        },
        seats=None if body.seats is None else SeatRange(body.seats.min, body.seats.max),
        custom_pricing=body.custom_pricing, description=body.description,
        features=tuple(body.features), sort_order=body.sort_order, on_sale=body.is_active,
        featured=body.is_featured, archived=archived,
    )  # fmt: skip


def merged_draft(current: PlanDraftBody, patch: PlanPatchBody) -> PlanDraftBody:
    """The current draft with the patch's fields over it, checked whole."""
    merged: dict[str, Any] = current.model_dump()
    for name, value in patch.model_dump(exclude_unset=True, exclude={"archived"}).items():
        if name in NESTED and isinstance(value, dict):
            merged[name] = {**merged[name], **value}
        else:
            merged[name] = value
    return validated(PlanDraftBody, merged)


def validated[M: BaseModel](model: type[M], data: dict[str, Any]) -> M:
    """The model of merged request data; a failure is the request's 422, located in the body."""
    try:
        return model.model_validate(data)
    except ValidationError as error:
        problems = [{**item, "loc": ("body", *item["loc"])} for item in error.errors()]
        raise RequestValidationError(problems) from error
