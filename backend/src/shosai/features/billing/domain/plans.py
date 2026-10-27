"""A plan of the catalogue, as the cabinet models it (BL-D2, ADR 0054; the admin's plan form).

A plan has a slug people see in links, an audience, seats when it is billed per seat,
prices for a month and a year in every currency, limits and capabilities. `None` in a
limit means unlimited and `0` means not included. A custom-priced plan has no price: it
is sold through a sales inquiry. An archived plan keeps its subscribers and is never on
sale. Every broken rule carries the API's error code.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.features.billing.domain.money import FREE, Prices

SLUG: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SLUG_LENGTH: Final = range(2, 41)
NAME_MAX: Final = 60
DESCRIPTION_MAX: Final = 300
FEATURES_MAX: Final = 20
FEATURE_MAX: Final = 120
SORT_MAX: Final = 999
# Бесплатный тариф кладёт миграция каталога; на него падает истёкший платный (BL-D2).
FREE_PLAN_ID: Final = UUID("0199f2a0-0000-7000-8000-000000000001")


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


class PlanRule(StrEnum):
    """A rule of the catalogue; the value is the API's error code."""

    SLUG = "plan_slug_invalid"
    NAME = "plan_name_invalid"
    DESCRIPTION = "plan_description_too_long"
    FEATURES = "plan_features_too_many"
    FEATURE = "plan_feature_invalid"
    SORT_ORDER = "plan_sort_order_invalid"
    PERIODS = "plan_periods_incomplete"
    TEAM_SEATS = "plan_team_needs_seats"
    CUSTOM_PRICE = "plan_custom_has_price"
    SEATS = "plan_seats_invalid"
    LIMITS = "plan_limits_invalid"


RULE_MESSAGES: Final = {
    PlanRule.SLUG: "slug — a-z, 0-9 и дефисы между ними, 2–40 символов",
    PlanRule.NAME: "название — от 1 до 60 символов",
    PlanRule.DESCRIPTION: "описание — до 300 символов",
    PlanRule.FEATURES: "не больше 20 пунктов возможностей",
    PlanRule.FEATURE: "пункт — до 120 символов",
    PlanRule.SORT_ORDER: "порядок — от 0 до 999",
    PlanRule.PERIODS: "цены задаются за месяц и за год",
    PlanRule.TEAM_SEATS: "у командного тарифа есть места",
    PlanRule.CUSTOM_PRICE: "у тарифа по запросу цен нет",
    PlanRule.SEATS: "места тарифа: от 1, верхняя граница не меньше нижней",
    PlanRule.LIMITS: "лимит тарифа — неотрицательное число или «без ограничений» по каждому классу",
}


class PlanRuleError(ValueError):
    """A plan breaks a catalogue rule."""

    def __init__(self, rule: PlanRule) -> None:
        super().__init__(RULE_MESSAGES[rule])
        self.rule = rule
        self.code = rule.value


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
    # Участников в звонке комнаты (meetings MR-D2): None — потолок платформы.
    room_participants: int | None = None

    def __post_init__(self) -> None:
        values = [
            self.meeting_minutes_per_month,
            self.file_manager_gb,
            self.knowledge_base_mb,
            self.daily_standard_tokens,
            self.room_participants,
            *self.weekly_tokens.values(),
        ]
        negative = any(value is not None and value < 0 for value in values)
        if negative or set(self.weekly_tokens) != set(ModelTier):
            raise PlanRuleError(PlanRule.LIMITS)

    def covers(self, other: PlanLimits) -> bool:
        """Whether these limits are at least `other`'s in every dimension."""
        pairs = [
            (self.meeting_minutes_per_month, other.meeting_minutes_per_month),
            (self.file_manager_gb, other.file_manager_gb),
            (self.knowledge_base_mb, other.knowledge_base_mb),
            (self.daily_standard_tokens, other.daily_standard_tokens),
            (self.room_participants, other.room_participants),
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
            raise PlanRuleError(PlanRule.SEATS)

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
    # Предлагается новым покупателям и выделен на странице тарифов.
    on_sale: bool = True
    featured: bool = False
    archived: bool = False

    def __post_init__(self) -> None:
        problem = plan_problem(self)
        if problem is not None:
            raise PlanRuleError(problem)

    @property
    def free(self) -> bool:
        """No price in any period and not sold through sales."""
        return not self.custom_pricing and all(prices.free for prices in self.prices.values())

    def billed_per_seat(self) -> bool:
        """A team plan: its price is per seat."""
        return self.seats is not None


def plan_problem(plan: Plan) -> PlanRule | None:
    """The first catalogue rule the plan breaks, or None."""
    rules = (
        (SLUG.fullmatch(plan.slug) is not None and len(plan.slug) in SLUG_LENGTH, PlanRule.SLUG),
        (0 < len(plan.name) <= NAME_MAX, PlanRule.NAME),
        (len(plan.description) <= DESCRIPTION_MAX, PlanRule.DESCRIPTION),
        (len(plan.features) <= FEATURES_MAX, PlanRule.FEATURES),
        (all(0 < len(item) <= FEATURE_MAX for item in plan.features), PlanRule.FEATURE),
        (0 <= plan.sort_order <= SORT_MAX, PlanRule.SORT_ORDER),
        (set(plan.prices) == set(BillingPeriod), PlanRule.PERIODS),
        (plan.audience is not Audience.TEAM or plan.seats is not None, PlanRule.TEAM_SEATS),
        (
            not plan.custom_pricing or all(p.free for p in plan.prices.values()),
            PlanRule.CUSTOM_PRICE,
        ),
    )
    return next((rule for holds, rule in rules if not holds), None)
