"""Writing a cost row once per effect key, in the payer's home (inv-9, F6-C1, F6-C6).

The writer runs after the provider call, never around it (§14 rule 1). One transaction in
the payer's home records the effect key in core's ledger; the effect inserts the row and
runs the settlements. A replayed key returns the stored row id and changes nothing. When
the home does not take the write, the row goes to the deferred-record task, which writes it
later with the same key; when the task cannot be queued either, the row is lost, logged and
counted, and the monitor of §16.4 shows it.
"""

from datetime import timedelta
from typing import Final, Protocol
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.costs.records import ProviderCost
from shosai.core.ai.costs.settlement import CostSettlements, SettledCost
from shosai.core.ai.metrics import AiMetrics
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import EffectKey, EffectLedger, EffectScope
from shosai.core.tasks.declaration import RETRY_TRANSIENT, TaskDeclaration, TaskHandler
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.core.tasks.payloads import TaskPayload
from shosai.core.tasks.queues import TaskQueue

# Повторы вызова — до 5 доставок, 3 попытки этапа, сутки ключа клиента — укладываются в 35 дней.
AI_COST: Final = EffectScope("ai.cost", timedelta(days=35))
RECORD_COST: Final = TaskDeclaration(
    name="ai.record_cost",
    queue=TaskQueue.CRITICAL,
    payload=CostEntry,
    deadline=timedelta(seconds=30),
    retry=RETRY_TRANSIENT,
)
log = structlog.stdlib.get_logger(__name__)


class WorkSender(Protocol):
    """What the writer needs from the task sender: queue one task within 50 ms."""

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Queue one run of the task; return its task id."""
        ...


class RecordedCost(BaseModel):
    """What the ledger keeps for a recorded call: its row id."""

    cost_id: UUID


class CostWriter:
    """Writes cost rows once per effect key; slices never write them themselves."""

    def __init__(
        self,
        transactions: HomeTransactions,
        effects: EffectLedger,
        settlements: CostSettlements,
        sender: WorkSender,
        metrics: AiMetrics,
    ) -> None:
        self._transactions = transactions
        self._effects = effects
        self._settlements = settlements
        self._sender = sender
        self._metrics = metrics

    async def record(self, entry: CostEntry) -> None:
        """Write the row now, or hand it to the deferred task when its home does not answer."""
        try:
            await self.write(entry)
        except HomeUnavailableError:
            await self._defer(entry)

    async def write(self, entry: CostEntry) -> UUID:
        """Write the row and run the settlements once; return the row id of the effect key."""
        async with self._transactions.begin(entry.scope()) as session:
            result = await self._effects.once(
                session,
                EffectKey(AI_COST, entry.effect_key),
                RecordedCost,
                lambda: self._insert(session, entry),
            )
        if not result.replayed:
            self._metrics.recorded(entry.cost_source)
            if entry.cost_rub is None:
                self._metrics.without_rate()
        return result.outcome.cost_id

    async def _insert(self, session: AsyncSession, entry: CostEntry) -> RecordedCost:
        values = entry.model_dump(exclude={"home", "cost_id"})
        values["payer"] = "platform" if entry.platform_account else "user"
        await session.execute(insert(ProviderCost).values(id=entry.cost_id, **values))
        settled = SettledCost(
            cost_id=entry.cost_id,
            user_id=entry.user_id,
            org_id=entry.org_id,
            platform_account=entry.platform_account,
            provider=entry.provider,
            model=entry.model,
            feature=entry.feature,
            call_class=entry.call_class,
            cost_usd=entry.cost_usd,
        )
        for settlement in self._settlements.all():
            await settlement.settle(session, settled)
        return RecordedCost(cost_id=entry.cost_id)

    async def _defer(self, entry: CostEntry) -> None:
        try:
            await self._sender.send(RECORD_COST, entry)
        except TaskQueueUnavailableError:
            self._metrics.lost()
            log.error(
                "Стоимость вызова потеряна: дом и очередь недоступны",
                home=entry.home.value,
                provider=entry.provider,
                model=entry.model,
                cost_id=str(entry.cost_id),
            )
            return
        self._metrics.deferred()
        log.warning("Стоимость вызова отложена в задачу", home=entry.home.value)


def record_cost_handler(writer: CostWriter) -> TaskHandler[CostEntry]:
    """The deferred-record task: the same write, retried while the home is down."""

    async def record_cost(entry: CostEntry) -> None:
        await writer.write(entry)

    return TaskHandler(RECORD_COST, record_cost)
