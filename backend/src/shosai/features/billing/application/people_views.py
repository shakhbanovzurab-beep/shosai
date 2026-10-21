"""What a person sees of billing: the plans on sale with their own, and the week's tokens.

Prices are in the account's currency — by its country, else by its home — never the
client's. The plan list is the catalogue's plans on sale in the pricing page's order; the
person's own plan joins it when it is no longer sold. Meeting minutes are the month's and
tokens the Monday week's per tier, both of the business calendar (ADR 0058), with the packs
left and the frontier models used this week. The catalogue (EU) and the person's home are
read at once.
"""

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.costs.records import ProviderCost
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.business_calendar import BusinessCalendar
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.application.catalogue import CATALOGUE_SCOPE
from shosai.features.billing.application.entitlement_snapshots import EntitlementSnapshots
from shosai.features.billing.application.minutes import MinutesMeter
from shosai.features.billing.application.tokens import COUNTED_ORIGIN, WEEK, packs_left
from shosai.features.billing.contracts import EntitlementSnapshot, EntitlementsUnavailableError
from shosai.features.billing.domain.currency import account_currency
from shosai.features.billing.domain.money import Currency
from shosai.features.billing.domain.plans import ModelTier, Plan
from shosai.features.billing.infrastructure.catalogue_rows import plan_of
from shosai.features.billing.infrastructure.plan_records import TariffRecord
from shosai.features.billing.infrastructure.token_records import TokenUsageRecord
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, Principal

FRONTIER_CLASS: Final = "expensive"


@dataclass(frozen=True, slots=True)
class MonthMinutes:
    """The month's meeting minutes against the plan's allowance."""

    used_seconds: int
    limit_minutes: int | None
    resets_at: datetime


@dataclass(frozen=True, slots=True)
class PlansForPerson:
    """The plans to choose from, the person's own one and the currency they pay in."""

    plans: tuple[Plan, ...]
    current: Plan
    currency: Currency
    minutes: MonthMinutes
    # Действующий тариф по времени: платный ли он и до какого момента.
    entitled: EntitlementSnapshot


@dataclass(frozen=True, slots=True)
class TierUse:
    """A tier's tokens this week against the plan's allowance (None: unlimited)."""

    tier: ModelTier
    used: int
    limit: int | None


@dataclass(frozen=True, slots=True)
class ModelUse:
    """A frontier model's tokens this week."""

    provider: str
    model: str
    tokens: int


@dataclass(frozen=True, slots=True)
class WeekUsage:
    """The week's tokens per tier, the packs left and the frontier models used."""

    week_start: datetime
    resets_at: datetime
    tiers: tuple[TierUse, ...]
    packs_left: int
    models: tuple[ModelUse, ...]


class PeopleViews:
    """The person's plans page and usage section."""

    def __init__(
        self,
        transactions: HomeTransactions,
        sources: tuple[EntitlementSnapshots, MinutesMeter, PortDirectory],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        *,
        business: BusinessCalendar,
    ) -> None:
        self._transactions = transactions
        self._snapshots, self._minutes, self._ports = sources
        self._clock = clock
        self._business = business

    async def plans(self, principal: Principal) -> PlansForPerson:
        """The plans on sale with the person's own, priced in their currency, and the minutes."""
        now = self._clock()
        snapshot = await self._snapshots.snapshot(principal.home, principal.user_id)
        catalogue, (country, used) = await asyncio.gather(
            self._catalogue(), self._home_facts(principal, now)
        )
        on_sale = tuple(plan for plan in catalogue if plan.on_sale and not plan.archived)
        current = next((plan for plan in catalogue if plan.slug == snapshot.plan_slug), None)
        if current is None:
            # Снимок назвал тариф, которого нет в каталоге: гадать о тарифе нельзя (inv-3).
            raise EntitlementsUnavailableError
        listed = on_sale if current in on_sale else (*on_sale, current)
        minutes = MonthMinutes(
            used, snapshot.limits.meeting_minutes_per_month, self._business.month_window(now)[1]
        )
        currency = account_currency(country, russian_home=principal.home is Home.RU)
        return PlansForPerson(listed, current, currency, minutes, snapshot)

    async def usage(self, principal: Principal) -> WeekUsage:
        """The week's tokens per tier with the plan's allowances, packs and frontier models."""
        now = self._clock()
        snapshot = await self._snapshots.snapshot(principal.home, principal.user_id)
        start, end = self._business.week_window(now)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            used = await week_tokens(session, principal.user_id, start)
            packs = await packs_left(session, principal.user_id)
            models = await frontier_models(session, principal.user_id, (start, end))
        tiers = tuple(
            TierUse(tier, used.get(tier, 0), snapshot.limits.weekly_tokens[tier])
            for tier in ModelTier
        )
        return WeekUsage(start, end, tiers, packs, models)

    async def _catalogue(self) -> tuple[Plan, ...]:
        statement = select(TariffRecord).order_by(
            TariffRecord.sort_order, TariffRecord.name, TariffRecord.id
        )
        async with self._transactions.begin(CATALOGUE_SCOPE, read_only=True) as session:
            rows = (await session.scalars(statement)).all()
        return tuple(plan_of(row) for row in rows)

    async def _home_facts(self, principal: Principal, now: datetime) -> tuple[str | None, int]:
        scope = TenancyScope(principal.home, principal.user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(
                session, principal.user_id
            )
            window = self._business.month_window(now)
            used = await self._minutes.used_in(session, principal.user_id, window)
        return (None if profile is None else profile.country), used


async def week_tokens(
    session: AsyncSession, user_id: UUID, week_start: datetime
) -> Mapping[ModelTier, int]:
    """Tokens per tier counted for the week starting at `week_start`."""
    rows = await session.execute(
        select(TokenUsageRecord.tier, TokenUsageRecord.tokens).where(
            TokenUsageRecord.user_id == user_id,
            TokenUsageRecord.period == WEEK,
            TokenUsageRecord.starts_on == week_start.date(),
        )
    )
    return {ModelTier(tier): int(tokens) for tier, tokens in rows.all()}


async def frontier_models(
    session: AsyncSession, user_id: UUID, window: tuple[datetime, datetime]
) -> tuple[ModelUse, ...]:
    """The frontier models the person used in the window, most tokens first."""
    tokens = func.sum(
        ProviderCost.input_tokens + ProviderCost.output_tokens
        + ProviderCost.input_audio_tokens + ProviderCost.output_audio_tokens
    ).label("tokens")  # fmt: skip
    statement = (
        select(ProviderCost.provider, ProviderCost.model, tokens)
        .where(
            ProviderCost.user_id == user_id,
            ProviderCost.call_class == FRONTIER_CLASS,
            ProviderCost.origin == COUNTED_ORIGIN,
            ProviderCost.created_at >= window[0],
            ProviderCost.created_at < window[1],
        )
        .group_by(ProviderCost.provider, ProviderCost.model)
        .order_by(tokens.desc(), ProviderCost.model)
    )
    rows = (await session.execute(statement)).all()
    return tuple(ModelUse(row.provider, row.model, int(row.tokens)) for row in rows)
