"""A plan of the catalogue, as the cabinet models it (BL-D2, ADR 0054; the admin's plan form).

A plan has a slug people see in links, an audience, seats when it is billed per seat,
prices for a month and a year in every currency, limits and capabilities. `None` in a
limit means unlimited and `0` means not included. A custom-priced plan has no price: it
is sold through a sales inquiry.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from shosai.features.billing.domain.money import FREE, Prices

SLUG: Final = re.compile(r"[a-z0-9-]{2,40}")
NAME_MAX: Final = 60
DESCRIPTION_MAX: Final = 300
FEATURES_MAX: Final = 20
FEATURE_MAX: Final = 120
SORT_MAX: Final = 999


class Audience(StrEnum):
    """Who a plan is for: the Upgrade page's tabs."""

    INDIVIDUAL = "individual"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class BillingPeriod(StrEnum):
    """How long one payment lasts."""

    MONTH = "month"
    YEAR = "year"


class Capability(StrEnum):
    """What a plan switches on beyond its limits."""

    SHARED_WORKSPACE = "shared_workspace"
    MEMBER_MANAGEMENT = "member_management"
    CENTRALIZED_BILLING = "centralized_billing"
    SSO = "sso"
    ADMIN_CONTROLS = "admin_controls"
    PRIORITY_SUPPORT = "priority_support"
    USAGE_ANALYTICS = "usage_analytics"
    # Модели класса frontier; у тарифов черновика это allow_frontier_models.
    FRONTIER_MODELS = "frontier_models"


class ModelTier(StrEnum):
    """The classes of models a weekly token allowance is counted in (BL-D4)."""

    STANDARD = "standard"
    FRONTIER = "frontier"


@dataclass(frozen=True, slots=True)
class PlanLimits:
    """What a plan allows; None is unlimited, 0 is not included."""

    meeting_minutes_per_month: int | None
    file_manager_gb: int | None
    knowledge_base_mb: int | None
    # Недельные токены по классам моделей и дневные токены стандартной модели (BL-D4).
    weekly_tokens: Mapping[ModelTier, int | None] = field(
        default_factory=lambda: {ModelTier.STANDARD: None, ModelTier.FRONTIER: 0}
    )
    daily_standard_tokens: int | None = None

    def __post_init__(self) -> None:
        values = [
            self.meeting_minutes_per_month,
            self.file_manager_gb,
            self.knowledge_base_mb,
            self.daily_standard_tokens,
            *self.weekly_tokens.values(),
        ]
        if any(value is not None and value < 0 for value in values):
            message = "лимит тарифа — неотрицательное число или «без ограничений»"
            raise ValueError(message)
        if set(self.weekly_tokens) != set(ModelTier):
            message = "недельные токены задаются для каждого класса моделей"
            raise ValueError(message)

    def covers(self, other: PlanLimits) -> bool:
        """Whether these limits are at least `other`'s in every dimension."""
        pairs = [
            (self.meeting_minutes_per_month, other.meeting_minutes_per_month),
            (self.file_manager_gb, other.file_manager_gb),
            (self.knowledge_base_mb, other.knowledge_base_mb),
            (self.daily_standard_tokens, other.daily_standard_tokens),
            *((self.weekly_tokens[tier], other.weekly_tokens[tier]) for tier in ModelTier),
        ]
        return all(_at_least(mine, theirs) for mine, theirs in pairs)


def _at_least(mine: int | None, theirs: int | None) -> bool:
    if mine is None:
        return True
    return theirs is not None and mine >= theirs


@dataclass(frozen=True, slots=True)
class SeatRange:
    """The seats a per-seat plan is sold for; no upper bound when `max` is None."""

    min: int
    max: int | None

    def __post_init__(self) -> None:
        if self.min < 1 or (self.max is not None and self.max < self.min):
            message = "места тарифа: от 1, верхняя граница не меньше нижней"
            raise ValueError(message)

    def allows(self, seats: int) -> bool:
        """Whether a purchase of this many seats fits the range."""
        return seats >= self.min and (self.max is None or seats <= self.max)


@dataclass(frozen=True, slots=True)
class Plan:
    """One plan of the catalogue."""

    slug: str
    name: str
    audience: Audience
    limits: PlanLimits
    capabilities: frozenset[Capability] = frozenset()
    prices: Mapping[BillingPeriod, Prices] = field(
        default_factory=lambda: {BillingPeriod.MONTH: FREE, BillingPeriod.YEAR: FREE}
    )
    seats: SeatRange | None = None
    custom_pricing: bool = False
    description: str = ""
    features: tuple[str, ...] = ()
    sort_order: int = 0
    archived: bool = False

    def __post_init__(self) -> None:
        problem = plan_problem(self)
        if problem is not None:
            raise ValueError(problem)

    @property
    def free(self) -> bool:
        """No price in any period and not sold through sales."""
        return not self.custom_pricing and all(prices.free for prices in self.prices.values())

    def billed_per_seat(self) -> bool:
        """A team plan: its price is per seat."""
        return self.seats is not None


def plan_problem(plan: Plan) -> str | None:
    """Why a plan breaks the catalogue's rules, or None."""
    rules = (
        (SLUG.fullmatch(plan.slug) is not None, "slug — a-z, 0-9 и дефис, 2–40 символов"),
        (0 < len(plan.name) <= NAME_MAX, "название — от 1 до 60 символов"),
        (len(plan.description) <= DESCRIPTION_MAX, "описание — до 300 символов"),
        (len(plan.features) <= FEATURES_MAX, "не больше 20 пунктов возможностей"),
        (all(0 < len(item) <= FEATURE_MAX for item in plan.features), "пункт — до 120 символов"),
        (0 <= plan.sort_order <= SORT_MAX, "порядок — от 0 до 999"),
        (set(plan.prices) == set(BillingPeriod), "цены задаются за месяц и за год"),
        (
            plan.audience is not Audience.TEAM or plan.seats is not None,
            "у командного тарифа есть места",
        ),
        (
            not plan.custom_pricing or all(p.free for p in plan.prices.values()),
            "у тарифа по запросу цен нет",
        ),
    )
    return next((message for holds, message in rules if not holds), None)
