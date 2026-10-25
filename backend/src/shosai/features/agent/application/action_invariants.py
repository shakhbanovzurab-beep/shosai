"""The hourly check of Leo's two invariants on actions (Leo L-N5, §16.4; agent step 9a2).

An item's effect is audited once per delivery of its slice's `agent.action_item.executed`, so
the audit trail tells what really ran. Every hour, per home and as the sweep role, the check
reads the `executed` rows of the last two hours — each row is read twice, so a missed tick
loses nothing — and counts the items executed more than once under their key and those whose
action was never `approved`. Both counts must stay 0: their gauges page (`StaysAtMost`), and
the actions behind them are logged by id for the runbook.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final

import structlog
from sqlalchemy import select
from sqlalchemy.orm import aliased

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.domain.actions import AuditEvent
from shosai.features.agent.infrastructure.action_metrics import ActionMetrics
from shosai.features.agent.infrastructure.run_records import AgentAuditRecord

AUDIT = AgentAuditRecord
WINDOW: Final = timedelta(hours=2)
# Сколько ид действий нарушения попадает в журнал за проверку: хватает, чтобы начать разбор.
LOGGED: Final = 20
log = structlog.stdlib.get_logger(__name__)


class ActionInvariants:
    """Counts the home's items executed twice or without an approval."""

    def __init__(
        self,
        transactions: HomeTransactions,
        metrics: ActionMetrics,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._metrics = metrics
        self._clock = clock

    async def check(self, home: Home) -> tuple[int, int]:
        """The home's items executed twice and executed without `approved`, in the window."""
        since = self._clock() - WINDOW
        earlier, approval = aliased(AUDIT), aliased(AUDIT)
        executed = (AUDIT.event == AuditEvent.EXECUTED.value, AUDIT.created_at >= since)
        twice = select(AUDIT.action_id, AUDIT.item_key).where(
            *executed,
            select(earlier.id)
            .where(
                earlier.item_key == AUDIT.item_key,
                earlier.event == AuditEvent.EXECUTED.value,
                earlier.id != AUDIT.id,
            )
            .exists(),
        )
        unapproved = select(AUDIT.action_id, AUDIT.item_key).where(
            *executed,
            ~select(approval.id)
            .where(
                approval.action_id == AUDIT.action_id,
                approval.event == AuditEvent.APPROVED.value,
            )
            .exists(),
        )
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            doubled = (await session.execute(twice)).all()
            unasked = (await session.execute(unapproved)).all()
        doubled_items = {item for _, item in doubled}
        self._metrics.invariants(home, len(doubled_items), len(unasked))
        if doubled_items:
            log.error(
                "Пункты действий Leo исполнены дважды", home=home.value,
                items=len(doubled_items), actions=sorted({str(a) for a, _ in doubled})[:LOGGED],
            )  # fmt: skip
        if unasked:
            log.error(
                "Пункты действий Leo исполнены без одобрения", home=home.value,
                items=len(unasked), actions=sorted({str(a) for a, _ in unasked})[:LOGGED],
            )  # fmt: skip
        return len(doubled_items), len(unasked)
