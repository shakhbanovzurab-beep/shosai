"""Leo's `memory` toolset bound to memory's services (memory step 6).

`memory.recall` runs at once in the person's scope and names each readable meeting a fact came
from as a source, so "why do you think…" can cite it. `memory.forget` freezes the exact facts
when it is proposed — all current and the person's, or the call is refused — draws the card
from their statements as they are then, and runs only through the Action Gateway: the item's
key, the facts' end and the audit event commit together, once.
"""

from datetime import timedelta
from typing import Final
from uuid import UUID

from shosai.core.agent_tools.bindings import ReadTool, WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import (
    PlannedEffect,
    Preview,
    ToolError,
    ToolErrorCode,
    ToolResult,
)
from shosai.core.agent_tools.sources import TITLE_MAX, SourceKind, SourceRef
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.action_items import ActionItems
from shosai.features.memory.application.fact_forgets import FactForgets
from shosai.features.memory.application.fact_search import FactSearch, FoundFact, SearchOutcome
from shosai.features.memory.application.switch import memory_on
from shosai.features.memory.channels import agent_previews as words
from shosai.features.memory.channels.agent_tools import (
    FORGET,
    RECALL,
    ForgetMemory,
    MemoryForgotten,
    RecallMemory,
    RememberedFact,
    RememberedFacts,
)
from shosai.features.memory.domain.facts import MemorySource

# Запас до срока вызова: ответ модели эмбеддингов должен успеть вернуться в ход.
MARGIN: Final = timedelta(milliseconds=500)
REFUSALS: Final = {
    SearchOutcome.OFF: ToolErrorCode.SWITCHED_OFF,
    SearchOutcome.NO_CONSENT: ToolErrorCode.FORBIDDEN,
    SearchOutcome.FAILED: ToolErrorCode.UNAVAILABLE,
}


def person(context: ToolContext) -> UUID:
    """The person the run acts for; a tool context always carries one."""
    user_id = context.scope.user_id
    if user_id is None:
        message = "контекст инструмента без человека"
        raise ValueError(message)
    return user_id


def remembered(found: FoundFact) -> RememberedFact:
    """A fact as the model reads it."""
    fact = found.fact
    return RememberedFact(
        fact_id=fact.id, statement=fact.statement, kind=fact.kind, source=fact.source,
        meeting=found.meeting, confirmed=fact.confirmed, pinned=fact.pinned,
        noted_on=fact.created_at.date(),
    )  # fmt: skip


def meetings(found: tuple[FoundFact, ...]) -> tuple[SourceRef, ...]:
    """The readable meetings the facts came from, once each."""
    refs = {
        item.meeting_id: SourceRef(
            SourceKind.MEETING, str(item.meeting_id), item.meeting[:TITLE_MAX], item.org_id
        )
        for item in found
        if item.meeting_id is not None and item.meeting
    }
    return tuple(refs.values())


class MemoryTools:
    """Reads, plans, previews and forgets for Leo."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[FactSearch, FactForgets, ActionItems],
    ) -> None:
        self._transactions = transactions
        self._search, self._forgets, self._items = services

    def bound(
        self,
    ) -> tuple[ReadTool[RecallMemory, RememberedFacts], WriteTool[ForgetMemory, MemoryForgotten]]:
        """The two tools."""
        return (
            ReadTool(RECALL, self.recall),
            WriteTool(FORGET, self.plan_forget, self.preview_forget, self.execute_forget),
        )

    async def recall(
        self, arguments: RecallMemory, context: ToolContext
    ) -> ToolResult[RememberedFacts]:
        """The facts nearest to the query, or the pinned and the latest."""
        left = timedelta(seconds=context.remaining_seconds()) - MARGIN
        wait = min(left, RECALL.timeout - MARGIN)
        if wait <= timedelta(0):
            return ToolResult.failed(ToolErrorCode.TIMEOUT)
        found = await self._search.search(context.scope, arguments.query, wait)
        if found.outcome in REFUSALS:
            return ToolResult.failed(REFUSALS[found.outcome])
        from_meeting = any(item.fact.source is MemorySource.MEETING for item in found.facts)
        return ToolResult(
            RememberedFacts(facts=[remembered(item) for item in found.facts]),
            sources=meetings(found.facts),
            provenance=Provenance.MEETING_SPEECH if from_meeting else Provenance.MEMORY,
        )

    async def plan_forget(
        self, arguments: ForgetMemory, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the facts to forget: every one current and the person's, or none."""
        user_id = person(context)
        named = list(dict.fromkeys(arguments.fact_ids))
        async with self._transactions.begin(context.scope, read_only=True) as session:
            if not await memory_on(session, user_id):
                return ToolError(ToolErrorCode.SWITCHED_OFF)
            rows = await self._forgets.current(session, user_id, named, lock=False)
        if len(rows) != len(named):
            return ToolError(ToolErrorCode.NOT_FOUND)
        return PlannedEffect(tuple(str(row.id) for row in rows))

    async def preview_forget(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: how many facts go and each statement as it reads now."""
        user_id = person(context)
        named = [UUID(target) for target in planned.targets]
        async with self._transactions.begin(context.scope, read_only=True) as session:
            rows = await self._forgets.current(session, user_id, named, lock=False)
        statements = "\n".join(row.statement for row in rows)
        return Preview(words.FORGET.key, {"count": len(rows), "statements": statements or None})

    async def execute_forget(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[MemoryForgotten]:
        """Forget the planned facts still current, once per item key."""
        user_id = person(context)
        named = [UUID(target) for target in planned.targets]
        async with self._transactions.begin(context.scope) as session:

            async def effect() -> MemoryForgotten:
                ended, until = await self._forgets.forget(session, user_id, named)
                return MemoryForgotten(fact_ids=ended, restorable_until=until)

            outcome = await self._items.once(
                session, (key, FORGET.name, len(named)), MemoryForgotten, effect
            )
        return ToolResult(outcome)
