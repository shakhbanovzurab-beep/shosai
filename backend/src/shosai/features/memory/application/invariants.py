"""The hourly check of memory's invariant (memory plan §3.8, target architecture §16.4).

No fact may be written after its person switched memory off: every writer reads the switch in
the transaction that writes. The person's own edits are theirs to make with memory off, so only
the writers that act for them count. Each hour, per home, the sweep role counts the facts such a
writer created after their person's switch-off and sets `shosai_memory_written_while_off{home}`,
which must stay 0; any other number is logged with the people's count, never a statement.
"""

import structlog
from sqlalchemy import func, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.memory.application.fact_rows import FACT
from shosai.features.memory.domain.facts import OWN_SOURCES
from shosai.features.memory.infrastructure.metrics import MemoryMetrics
from shosai.features.memory.infrastructure.records import MemorySettingsRecord

SETTINGS = MemorySettingsRecord
log = structlog.stdlib.get_logger(__name__)


class MemoryInvariants:
    """Counts the facts written while memory was off."""

    def __init__(self, transactions: HomeTransactions, metrics: MemoryMetrics) -> None:
        self._transactions = transactions
        self._metrics = metrics

    async def check(self, home: Home) -> int:
        """How many facts of the home were written after their person switched memory off."""
        query = (
            select(func.count(FACT.id), func.count(func.distinct(FACT.user_id)))
            .join(SETTINGS, SETTINGS.user_id == FACT.user_id)
            .where(SETTINGS.enabled.is_(False), FACT.created_at > SETTINGS.changed_at)
            .where(FACT.source_kind.not_in(tuple(source.value for source in OWN_SOURCES)))
        )
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            facts, people = (await session.execute(query)).one()
        self._metrics.written_while_off(home, int(facts))
        if facts:
            log.error(
                "Факты памяти записаны после выключения памяти",
                home=home.value,
                facts=int(facts),
                people=int(people),
            )
        return int(facts)
