"""An approved action carried out through its slices, once (Leo §8.4 rules 1, 2, 5; step 9a).

An agent worker claims the approved action — one conditional update, so of two deliveries of
the task only one goes on — and applies its items in order. Each item is marked `executing` in
its own commit before its slice is called, then its outcome in the next: the slice applies the
effect once per key `action:index` in its own transaction, with its audit event. A typed refusal
fails the item; a timeout or an unexpected error leaves its outcome unknown, since the effect
may have committed — it is never retried. The action ends with its items' honest outcome and
a note in its thread, its paused run goes back to the `agent` queue for the epilogue, and the
cabinet sees the card's end and what to refresh.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import structlog

from shosai.core.agent_tools.bindings import WriteTool
from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.agent_tools.context import Taint, ToolContext
from shosai.core.agent_tools.results import PlannedEffect
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.action_rows import (
    AuditEntry,
    audit,
    items_of,
    moved,
    store_items,
)
from shosai.features.agent.application.paused_runs import PausedRuns
from shosai.features.agent.domain.action_items import ActionItem, ItemState
from shosai.features.agent.domain.actions import (
    ActionEvent,
    ActionStatus,
    AuditEvent,
    finishing_event,
    item_key,
    transition,
)
from shosai.features.agent.infrastructure.action_metrics import ActionMetrics
from shosai.features.agent.infrastructure.run_records import AgentActionRecord

TOOL_UNAVAILABLE = "tool_unavailable"
TIMED_OUT = "timeout"
FAILED = "failed"
AUDITED_ENDS = {
    ActionStatus.FAILED: AuditEvent.FAILED,
    ActionStatus.OUTCOME_UNKNOWN: AuditEvent.OUTCOME_UNKNOWN,
}
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Claimed:
    """An action this executor won, in its person's scope."""

    record: AgentActionRecord
    scope: TenancyScope


class ActionExecution:
    """Carries out approved actions."""

    def __init__(
        self,
        transactions: HomeTransactions,
        parts: tuple[AgentToolCatalog, PausedRuns, ActionMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._catalog, self._paused, self._metrics = parts
        self._clock = clock

    async def run(self, home: Home, user_id: UUID, action_id: UUID) -> None:
        """Claim the approved action and carry it out; nothing when another claimed it."""
        scope = TenancyScope(home, user_id)
        async with self._transactions.begin(scope) as session:
            record = await moved(
                session, action_id, transition(ActionStatus.APPROVED, ActionEvent.CLAIM),
                {"updated_at": self._clock()},
            )  # fmt: skip
        if record is None:
            return
        await self._paused.tell(home, record)
        claimed = Claimed(record, scope)
        items = list(items_of(record))
        for index, item in enumerate(items):
            items[index] = item.with_state(ItemState.EXECUTING)
            if not await self._store(claimed, items):
                return
            items[index] = await self._apply(claimed, item, index)
            if not await self._store(claimed, items):
                return
        await self._finish(claimed, items)

    async def _store(self, claimed: Claimed, items: list[ActionItem]) -> bool:
        async with self._transactions.begin(claimed.scope) as session:
            kept = await store_items(session, claimed.record.id, items, self._clock())
        if not kept:
            log.warning("Исполнение действия Leo прервано обходом", action=claimed.record.id)
        return kept

    async def _apply(self, claimed: Claimed, item: ActionItem, index: int) -> ActionItem:
        """The item's outcome: its slice applied it, refused it, or nobody can tell."""
        record = claimed.record
        tool = self._catalog.tool(item.tool)
        if not isinstance(tool, WriteTool):
            return item.with_state(ItemState.FAILED, TOOL_UNAVAILABLE)
        timeout = tool.spec.timeout
        context = ToolContext(
            claimed.scope, record.run_id or record.id, self._clock() + timeout, Taint(record.taint)
        )
        planned = PlannedEffect(item.targets, item.plan)
        try:
            async with asyncio.timeout(timeout.total_seconds()):
                result = await tool.execute(planned, context, item_key(str(record.id), index))
        except TimeoutError:
            return item.with_state(ItemState.OUTCOME_UNKNOWN, TIMED_OUT)
        # Неожиданная ошибка среза: эффект мог зафиксироваться — исход неизвестен, повтора нет.
        except Exception:
            log.exception("Пункт действия Leo упал", tool=item.tool, action=record.id)
            return item.with_state(ItemState.OUTCOME_UNKNOWN, FAILED)
        if result.error is not None:
            return item.with_state(ItemState.FAILED, result.error.code.value)
        return item.with_state(ItemState.SUCCEEDED)

    async def _finish(self, claimed: Claimed, items: list[ActionItem]) -> None:
        event = finishing_event([item.outcome for item in items])
        now = self._clock()
        async with self._transactions.begin(claimed.scope) as session:
            record = await moved(
                session, claimed.record.id, transition(ActionStatus.EXECUTING, event),
                {"items": [item.stored() for item in items], "updated_at": now},
            )  # fmt: skip
            if record is None:
                return
            ended = ActionStatus(record.status)
            if ended in AUDITED_ENDS:
                code = next((item.code for item in items if item.code), None)
                audit(session, record, AuditEntry(AUDITED_ENDS[ended], code=code), now)
            settled = await self._paused.settle(session, record)
        self._metrics.decided(record.origin, ended.value)
        if record.approved_at is not None:
            waited = (now - record.approved_at).total_seconds()
            self._metrics.ended_after_approval(record.status, waited)
        await self._paused.tell(claimed.scope.home, record, settled, self._invalidates(items))

    def _invalidates(self, items: list[ActionItem]) -> tuple[str, ...]:
        """The cabinet's query domains the succeeded items changed."""
        domains: dict[str, None] = {}
        for item in items:
            tool = self._catalog.tool(item.tool)
            if item.state is ItemState.SUCCEEDED and tool is not None:
                domains |= dict.fromkeys(tool.spec.invalidates)
        return tuple(domains)
