"""The hourly reconciliation of billed calls and cost rows, per home (§16.4, F6 §3.11).

Each hour the job of each home takes the hour two hours back — time for deferred rows to
land — and compares what it should hold (`billed - repeated` from the billing marks) with
the rows `provider_costs` holds for it. The gap is the monitor's gauge
`shosai_ai_cost_rows_missing{home}`: zero when every billed call has its row; F5's alert
pages on anything above. A home or Valkey out of reach leaves the gauge as it was and says
so in the log, since an unknown hour must not read as a clean one.
"""

from datetime import UTC, datetime, timedelta
from typing import Final

import structlog
from prometheus_client import CollectorRegistry, Gauge
from sqlalchemy import func, select

from shosai.core.ai.costs.billing import BillingMarks, hour_of
from shosai.core.ai.costs.records import ProviderCost
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue

RECONCILE_LAG: Final = timedelta(hours=2)
HOUR: Final = timedelta(hours=1)
RECONCILE_COSTS: Final = TaskDeclaration(
    name="ai.reconcile_costs",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=2),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
RECONCILE_COSTS_JOB: Final = PeriodicJob(RECONCILE_COSTS, HOUR)
log = structlog.stdlib.get_logger(__name__)


class CostReconciliation:
    """Compares a home's billed hour with its rows and sets the monitor's gauge."""

    def __init__(
        self, transactions: HomeTransactions, marks: BillingMarks, registry: CollectorRegistry
    ) -> None:
        self._transactions = transactions
        self._marks = marks
        self._missing = Gauge(
            "shosai_ai_cost_rows_missing",
            "Оплаченные вызовы последнего сверенного часа без строки стоимости",
            ("home",),
            registry=registry,
        )
        self._hour = Gauge(
            "shosai_ai_cost_reconciled_hour_timestamp_seconds",
            "Начало последнего сверенного часа дома, Unix-время",
            ("home",),
            registry=registry,
        )

    async def reconcile(self, home: Home, now: datetime | None = None) -> int | None:
        """The rows the home's hour lacks; None when the hour could not be read."""
        hour = hour_of((now or datetime.now(UTC)) - RECONCILE_LAG)
        try:
            marks = await self._marks.of_hour(home, hour)
            rows = await self._rows(home, hour)
        except (*REDIS_FAILURES, HomeUnavailableError) as failure:
            log.warning(
                "Сверка стоимости пропущена: источник недоступен",
                home=home.value,
                hour=hour.isoformat(),
                error_type=type(failure).__name__,
            )
            return None
        missing = max(marks.expected_rows - rows, 0)
        self._missing.labels(home=home.value).set(missing)
        self._hour.labels(home=home.value).set(hour.timestamp())
        fields = {"home": home.value, "hour": hour.isoformat(), "billed": marks.billed}
        if missing:
            log.error(
                "Оплаченные вызовы без строки стоимости", missing=missing, rows=rows, **fields
            )
        else:
            log.info("Сверка стоимости: строк столько, сколько оплачено", rows=rows, **fields)
        return missing

    async def _rows(self, home: Home, hour: datetime) -> int:
        query = select(func.count()).where(
            ProviderCost.created_at >= hour, ProviderCost.created_at < hour + HOUR
        )
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            return int(await session.scalar(query) or 0)


def reconcile_costs_handler(reconciliation: CostReconciliation) -> TaskHandler[HomeTaskPayload]:
    """The tick of a home's hourly reconciliation."""

    async def reconcile_costs(payload: HomeTaskPayload) -> None:
        await reconciliation.reconcile(payload.home)

    return TaskHandler(RECONCILE_COSTS, reconcile_costs)
