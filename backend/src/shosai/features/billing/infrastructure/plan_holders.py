"""How many people hold each plan, counted in both homes at once (`billing_plan_holders`).

Row-level security keeps every subscription personal, so the count runs through the
function the migration owns: it returns per plan the subscriptions in force with the
queued plans, and every row that names the plan, and never a row itself.
"""

import asyncio
from collections.abc import Collection, Mapping
from typing import Final
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import Uuid

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.application.catalogue import PlanHolding

HOLDERS_SQL: Final = text(
    "SELECT plan_id, current_holders, referencing_rows FROM billing_plan_holders(:plans)"
).bindparams(bindparam("plans", type_=ARRAY(Uuid())))


class SubscriptionHolders:
    """The catalogue's subscriber counts over the subscriptions of both homes."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    async def counts(self, plan_ids: Collection[UUID]) -> Mapping[UUID, PlanHolding]:
        """The holding per plan; plans nobody holds are absent."""
        if not plan_ids:
            return {}
        per_home = await asyncio.gather(*(self._home(home, plan_ids) for home in Home))
        total: dict[UUID, PlanHolding] = {}
        for counts in per_home:
            for plan_id, holding in counts.items():
                known = total.get(plan_id, PlanHolding(0, 0))
                total[plan_id] = PlanHolding(
                    known.current + holding.current, known.referenced + holding.referenced
                )
        return total

    async def _home(self, home: Home, plan_ids: Collection[UUID]) -> dict[UUID, PlanHolding]:
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            rows = (await session.execute(HOLDERS_SQL, {"plans": list(plan_ids)})).all()
        return {row.plan_id: PlanHolding(row.current_holders, row.referencing_rows) for row in rows}
