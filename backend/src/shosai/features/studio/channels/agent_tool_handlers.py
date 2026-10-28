"""Leo's `studio` toolset bound to studio's services (studio step 13).

`studio.read_context` runs at once in the person's scope. `studio.update_context` checks and
freezes the new text when it is proposed — trimmed, within 4 000 characters, or the call is
refused — shows it on the card, and runs only through the Action Gateway: the item's key and
the write commit together, once.
"""

from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from shosai.core.agent_tools.bindings import ReadTool, WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import (
    PlannedEffect,
    Preview,
    ToolError,
    ToolErrorCode,
    ToolResult,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.action_items import ActionItems
from shosai.features.studio.channels import agent_previews as words
from shosai.features.studio.channels.agent_tools import (
    READ_CONTEXT,
    UPDATE_CONTEXT,
    ContextUpdated,
    PersonalContext,
    ReadContext,
    UpdateContext,
)
from shosai.features.studio.domain.errors import StudioRuleError
from shosai.features.studio.domain.prompts import checked_context
from shosai.features.studio.infrastructure.person_records import ContextRecord

TARGET: Final = "context"


def person(context: ToolContext) -> UUID:
    """The person the run acts for; a tool context always carries one."""
    user_id = context.scope.user_id
    if user_id is None:
        message = "контекст инструмента без человека"
        raise ValueError(message)
    return user_id


def planned_text(planned: PlannedEffect) -> str:
    """The text frozen when the write was proposed."""
    return str(planned.data["content"])


class StudioTools:
    """Reads, plans, previews and rewrites the person's words about themselves for Leo."""

    def __init__(self, transactions: HomeTransactions, items: ActionItems) -> None:
        self._transactions = transactions
        self._items = items

    def bound(
        self,
    ) -> tuple[ReadTool[ReadContext, PersonalContext], WriteTool[UpdateContext, ContextUpdated]]:
        """The two tools."""
        return (
            ReadTool(READ_CONTEXT, self.read),
            WriteTool(UPDATE_CONTEXT, self.plan, self.preview, self.execute),
        )

    async def read(
        self, arguments: ReadContext, context: ToolContext
    ) -> ToolResult[PersonalContext]:
        """The person's words about themselves."""
        del arguments
        user_id = person(context)
        async with self._transactions.begin(context.scope, read_only=True) as session:
            row = await session.scalar(
                select(ContextRecord).where(ContextRecord.user_id == user_id)
            )
        if row is None:
            return ToolResult(PersonalContext(content="", updated_at=None))
        return ToolResult(PersonalContext(content=row.content, updated_at=row.updated_at))

    async def plan(
        self, arguments: UpdateContext, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the new text as it will be stored, or refuse it."""
        person(context)
        try:
            text = checked_context(arguments.content)
        except StudioRuleError:
            return ToolError(ToolErrorCode.INVALID_ARGUMENTS)
        return PlannedEffect((TARGET,), {"content": text})

    async def preview(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: the new text as it will be saved."""
        del context
        return Preview(words.UPDATE_CONTEXT.key, {"content": planned_text(planned) or None})

    async def execute(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[ContextUpdated]:
        """Save the frozen text, once per item key."""
        user_id, text = person(context), planned_text(planned)
        async with self._transactions.begin(context.scope) as session:

            async def effect() -> ContextUpdated:
                now = datetime.now(UTC)
                statement = insert(ContextRecord).values(
                    user_id=user_id, content=text, created_at=now, updated_at=now
                )
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[ContextRecord.user_id],
                        set_={"content": text, "updated_at": now},
                    )
                )
                return ContextUpdated(content=text, updated_at=now)

            outcome = await self._items.once(
                session, (key, UPDATE_CONTEXT.name, 1), ContextUpdated, effect
            )
        return ToolResult(outcome)
