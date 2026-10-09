"""Outbox gauges read from each home: unpublished events and the oldest one's age (§16.4).

The backlog is a property of a home's database, not of a worker, so one process — the
scheduler — sets the gauges. Age matters more than count: a hundred fresh events are
work under load, one event an hour old means delivery is broken. Each home is read on
its own; a home out of reach keeps its last values and is reported by its own metrics.
"""

import asyncio

from sqlalchemy import exc, func, select

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.metrics import EventMetrics
from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.observability.outage_log import OutageLog

# Возраст по часам сервера базы: часы процессов на это не влияют.
PENDING = select(
    func.count(),
    func.coalesce(func.extract("epoch", func.now() - func.min(OutboxMessage.occurred_at)), 0),
).where(OutboxMessage.published_at.is_(None))


class OutboxMonitor:
    """Refreshes the outbox gauges of every home."""

    def __init__(self, transactions: HomeTransactions, metrics: EventMetrics) -> None:
        self._transactions = transactions
        self._metrics = metrics
        self._outages = {home: OutageLog("База дома не ответила замеру outbox") for home in Home}

    async def refresh(self) -> bool:
        """Read every home at once and set its gauges; False when a home did not answer."""
        answered = await asyncio.gather(*(self._refresh_home(home) for home in Home))
        return all(answered)

    async def _refresh_home(self, home: Home) -> bool:
        try:
            async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
                count, age = (await session.execute(PENDING)).one()
        except HomeUnavailableError:
            # Отказ дома уже записан и посчитан HomeTransactions.
            return False
        except exc.OperationalError as error:
            self._outages[home].failed(error, home=home.value)
            return False
        self._metrics.set_pending(home, int(count), max(float(age), 0.0))
        return True
