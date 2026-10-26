"""The ratings of Leo's answers as the operator reads them: counts only (ADR 0068 AG-D13, AG-D5).

The operator sees ratings as numbers, never a conversation or a person: how many answers were
rated useful and not useful over the last days, in both homes together, and by the model that
answered. The rows are read by the agent's read-only sweep, which row-level security lets see
every person's rows for counting and nothing else.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.infrastructure.person_records import AgentFeedbackRecord
from shosai.features.agent.infrastructure.run_records import AgentRunRecord

FEEDBACK = AgentFeedbackRecord
RUN = AgentRunRecord
UNKNOWN_MODEL = "unknown"


@dataclass(frozen=True, slots=True)
class RatingCounts:
    """Ratings over a period: by rating, and by model and rating."""

    by_rating: dict[str, int]
    by_model: dict[tuple[str, str], int]


class PlatformRatings:
    """Counts the ratings of both homes."""

    def __init__(
        self,
        transactions: HomeTransactions,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._clock = clock

    async def counts(self, days: int) -> RatingCounts:
        """The ratings given over the last `days` days."""
        since = self._clock() - timedelta(days=days)
        statement = (
            select(FEEDBACK.rating, RUN.model, func.count())
            .select_from(FEEDBACK)
            .outerjoin(RUN, RUN.id == FEEDBACK.run_id)
            .where(FEEDBACK.updated_at >= since)
            .group_by(FEEDBACK.rating, RUN.model)
        )
        by_rating: Counter[str] = Counter()
        by_model: Counter[tuple[str, str]] = Counter()
        for home in Home:
            async with self._transactions.begin(
                TenancyScope(home), read_only=True, sweep=True
            ) as session:
                for rating, model, count in await session.execute(statement):
                    by_rating[str(rating)] += int(count)
                    by_model[(str(model or UNKNOWN_MODEL), str(rating))] += int(count)
        return RatingCounts(dict(by_rating), dict(by_model))
