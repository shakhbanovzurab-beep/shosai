"""The accounts of every home, counted for the platform operator's Leo (agent plan AG-D5).

Each home's `users` is read in a platform transaction, as the admin's search reads it, and
only counted: by state, and the accounts registered in the last days.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts.accounts import HomeAccounts
from shosai.features.identity.infrastructure.records import User


class AccountCountsReader:
    """Counts the accounts of both homes."""

    def __init__(
        self,
        transactions: HomeTransactions,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._clock = clock

    async def counts(self, days: int) -> Sequence[HomeAccounts]:
        """Each home's accounts by state, and those registered in the last `days` days."""
        since = self._clock() - timedelta(days=days)
        found = []
        for home in Home:
            async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
                states = await session.execute(
                    select(User.state, func.count()).group_by(User.state)
                )
                registered = await session.scalar(
                    select(func.count()).select_from(User).where(User.created_at >= since)
                )
            by_state = {str(state): int(count) for state, count in states}
            found.append(HomeAccounts(home, by_state, int(registered or 0)))
        return found
