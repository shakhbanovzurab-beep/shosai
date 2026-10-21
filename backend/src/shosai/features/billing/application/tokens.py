"""A person's model tokens: counted from cost rows, spent from packs, read before a request.

The tier follows the call class: an expensive call is a frontier one, a standard call a
standard one; essential calls (meetings) and Leo's background work are not counted
(F6-D6, Leo §5.4). `TokenSettlement` runs in the cost row's own transaction, once per
row: it adds the row's tokens to the Monday week and, for standard, the day — both of the
business calendar (ADR 0058) — then
debits packs for what the row used past the frontier week's allowance, with the cost id
as the debit's unique key. The week's row is locked by its update, so two settlements of
a person never spend the same pack tokens. `TokenStanding` reads the use live and gives
the agent the route of the next request (BL-D4).
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.costs.settlement import SettledCost
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions, transaction_info
from shosai.core.kernel.business_calendar import BusinessCalendar
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.contracts import Entitlements, EntitlementsUnavailableError
from shosai.features.billing.domain.meters import (
    TokenAllowance,
    TokenDecision,
    beyond_allowance,
    token_decision,
)
from shosai.features.billing.domain.plans import ModelTier
from shosai.features.billing.infrastructure.token_records import (
    CreditLedgerRecord,
    TokenUsageRecord,
)

TIER_OF_CLASS: Final = {"expensive": ModelTier.FRONTIER, "standard": ModelTier.STANDARD}
COUNTED_ORIGIN: Final = "interactive"
WEEK: Final = "week"
DAY: Final = "day"

log = structlog.stdlib.get_logger(__name__)


def week_of(moment: datetime, business: BusinessCalendar) -> date:
    """The Monday of the business week of a moment."""
    return business.week_window(moment)[0].date()


async def add_tokens(
    session: AsyncSession, user_id: UUID, key: tuple[ModelTier, str, date], tokens: int
) -> int | None:
    """Add tokens to a period's count; the count before them, or None for an older period."""
    tier, period, starts_on = key
    row = TokenUsageRecord
    added = insert(row).values(
        id=new_id(), user_id=user_id, tier=tier.value, period=period, starts_on=starts_on,
        tokens=tokens,
    )  # fmt: skip
    fresh = added.excluded
    statement = added.on_conflict_do_update(
        index_elements=["user_id", "tier", "period"],
        set_={
            "tokens": case(
                (row.starts_on == fresh.starts_on, row.tokens + fresh.tokens),
                (row.starts_on < fresh.starts_on, fresh.tokens),
                else_=row.tokens,
            ),
            "starts_on": func.greatest(row.starts_on, fresh.starts_on),
            "updated_at": func.now(),
        },
    ).returning(TokenUsageRecord.tokens, TokenUsageRecord.starts_on)
    after, counted_on = (await session.execute(statement)).one()
    return int(after) - tokens if counted_on == starts_on else None


async def packs_left(session: AsyncSession, user_id: UUID) -> int:
    """The person's pack tokens: purchases less debits and refunds."""
    total = await session.scalar(
        select(func.coalesce(func.sum(CreditLedgerRecord.tokens), 0)).where(
            CreditLedgerRecord.user_id == user_id
        )
    )
    return max(int(total or 0), 0)


class TokenSettlement:
    """The `CostSettlement` of billing: tokens counted, packs debited, once per cost row."""

    def __init__(self, entitlements: Entitlements, business: BusinessCalendar) -> None:
        self._entitlements = entitlements
        self._business = business

    @property
    def name(self) -> str:
        """The settlement's name in logs."""
        return "billing.tokens"

    async def settle(self, session: AsyncSession, cost: SettledCost) -> None:
        """Count the row's tokens and pay for those past the frontier allowance with packs."""
        tier = TIER_OF_CLASS.get(cost.call_class)
        user_id = cost.user_id
        if tier is None or user_id is None or cost.origin != COUNTED_ORIGIN or cost.tokens <= 0:
            return
        moment = cost.created_at
        week = week_of(moment, self._business)
        before = await add_tokens(session, user_id, (tier, WEEK, week), cost.tokens)
        if tier is ModelTier.STANDARD:
            day = self._business.date_of(moment)
            await add_tokens(session, user_id, (tier, DAY, day), cost.tokens)
        elif before is not None:
            await self._debit_packs(session, cost, user_id, before)

    async def _debit_packs(
        self, session: AsyncSession, cost: SettledCost, user_id: UUID, before: int
    ) -> None:
        home = transaction_info(session).scope.home
        try:
            snapshot = await self._entitlements.snapshot(home, user_id)
        except EntitlementsUnavailableError:
            log.warning("Пакеты не списаны: тариф не прочитан", cost_id=str(cost.cost_id))
            return
        limit = snapshot.limits.weekly_tokens[ModelTier.FRONTIER]
        debit = min(
            beyond_allowance(limit, before, cost.tokens), await packs_left(session, user_id)
        )
        if debit <= 0:
            return
        await session.execute(
            insert(CreditLedgerRecord)
            .values(id=new_id(), user_id=user_id, kind="debit", tokens=-debit, cost_id=cost.cost_id)
            .on_conflict_do_nothing(index_elements=["cost_id"])
        )


class TokenStanding:
    """The `billing.token_allowance` binding: the next request's route, read live."""

    def __init__(
        self,
        transactions: HomeTransactions,
        entitlements: Entitlements,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        *,
        business: BusinessCalendar,
    ) -> None:
        self._transactions = transactions
        self._entitlements = entitlements
        self._clock = clock
        self._business = business

    async def decision(self, home: Home, user_id: UUID, tier: ModelTier) -> TokenDecision:
        """Within the allowance, from packs, fall back or stop, with the limit why."""
        snapshot = await self._entitlements.snapshot(home, user_id)
        now = self._clock()
        periods = {WEEK: week_of(now, self._business), DAY: self._business.date_of(now)}
        try:
            scope = TenancyScope(home, user_id)
            usage = select(TokenUsageRecord).where(
                TokenUsageRecord.user_id == user_id, TokenUsageRecord.tier == tier.value
            )
            async with self._transactions.begin(scope, read_only=True) as session:
                rows = (await session.scalars(usage)).all()
                packs = await packs_left(session, user_id) if tier is ModelTier.FRONTIER else 0
        except (SQLAlchemyError, HomeUnavailableError, OSError, TimeoutError) as error:
            log.warning("Токены не прочитаны: база недоступна", home=home.value)
            raise EntitlementsUnavailableError from error
        used = {row.period: row.tokens for row in rows if row.starts_on == periods[row.period]}
        limits = snapshot.limits
        standard = tier is ModelTier.STANDARD
        allowance = TokenAllowance(
            tier=tier,
            weekly_limit=limits.weekly_tokens[tier],
            used_this_week=used.get(WEEK, 0),
            packs_left=packs,
            daily_limit=limits.daily_standard_tokens if standard else None,
            used_today=used.get(DAY, 0),
        )
        return token_decision(allowance)
