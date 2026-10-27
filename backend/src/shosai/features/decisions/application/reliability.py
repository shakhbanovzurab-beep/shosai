"""The daily reliability pass of a home (decisions plan §3.5 "Online", ADR 0069 DL-D7).

Once a day per home, the pass reads the decisions of each of the last two full days — as the
sweep role, which alone may read them — with what followed them, grouped in the database by
everything counted, so a day of a busy home is a few hundred rows, never its decisions one by
one. The groups become counts per band (`domain/reliability.py`), and the EU home's rows of
that day and home are replaced in one transaction: a pass run twice, or a day counted again
once a late outcome has come in, leaves exactly the same rows.
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Final

import structlog
from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.domain.reliability import DecisionGroup, tallied
from shosai.features.decisions.infrastructure.records import (
    DecisionOutcomeRow,
    DecisionRow,
    ReliabilityRow,
)

# Исход приходит позже решения (карточка ждёт час): пересчитываем два последних полных дня.
DAYS_COUNTED: Final = 2
# Исходы решения дня ищем в этом дне и следующем: секционирование отбрасывает остальные.
OUTCOME_WINDOW: Final = timedelta(days=2)
DECISION = DecisionRow
OUTCOME = DecisionOutcomeRow
log = structlog.stdlib.get_logger(__name__)


class ReliabilityPass:
    """Counts a home's recent days into the EU home's reliability rows."""

    def __init__(
        self,
        transactions: HomeTransactions,
        policies: Mapping[str, Policy[Any, Any]],
        clock: Callable[[], datetime],
    ) -> None:
        self._transactions = transactions
        self._policies = policies
        self._clock = clock

    async def run(self, home: Home) -> int:
        """Count the last full days of the home; how many band rows were kept."""
        today = self._clock().astimezone(UTC).date()
        kept = 0
        for back in range(DAYS_COUNTED, 0, -1):
            kept += await self.count_day(home, today - timedelta(days=back))
        return kept

    async def count_day(self, home: Home, day: date) -> int:
        """Replace one day's rows of the home; how many were kept."""
        groups = await self._groups(home, day)
        tallies = tallied(groups, self._policies)
        rows = [
            {"day": day, "home": home.value, "point": key.point, "version": key.version,
             "revision": key.revision or 0, "shadow": key.shadow, "band": key.band,
             "language": key.language, "source": key.source, "decisions": tally.decisions,
             "positives": tally.positives}
            for key, tally in tallies.items()
        ]  # fmt: skip
        async with self._transactions.begin(TenancyScope(Home.EU)) as session:
            await session.execute(
                delete(ReliabilityRow).where(
                    ReliabilityRow.day == day, ReliabilityRow.home == home.value
                )
            )
            if rows:
                await session.execute(insert(ReliabilityRow).values(rows))
        log.info(
            "Надёжность решений посчитана", home=home.value, day=day.isoformat(), bands=len(rows)
        )
        return len(rows)

    async def _groups(self, home: Home, day: date) -> Sequence[DecisionGroup]:
        """The day's decisions grouped by everything counted, with what followed them."""
        start = datetime.combine(day, time.min, tzinfo=UTC)
        end = start + timedelta(days=1)
        joined = and_(
            OUTCOME.point == DECISION.point,
            OUTCOME.subject_kind == DECISION.subject_kind,
            OUTCOME.subject_id == DECISION.subject_id,
            OUTCOME.part == DECISION.part,
            OUTCOME.created_at >= start,
            OUTCOME.created_at < start + OUTCOME_WINDOW,
        )
        counted = (
            DECISION.point, DECISION.version, DECISION.revision, DECISION.shadow,
            DECISION.outcome, DECISION.language, DECISION.source, OUTCOME.observation,
        )  # fmt: skip
        statement = (
            select(*counted, func.count())
            .select_from(DECISION)
            .outerjoin(OUTCOME, joined)
            .where(DECISION.created_at >= start, DECISION.created_at < end)
            .group_by(*counted)
        )
        scope = TenancyScope(home)
        async with self._transactions.begin(scope, read_only=True, sweep=True) as session:
            rows = (await session.execute(statement)).all()
        return [
            DecisionGroup(
                point=row[0], version=row[1], revision=row[2], shadow=row[3], outcome=row[4],
                language=row[5], source=row[6], observation=row[7], count=int(row[8]),
            )
            for row in rows
        ]  # fmt: skip
