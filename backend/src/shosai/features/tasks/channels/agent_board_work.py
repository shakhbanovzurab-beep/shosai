"""What Leo's board and column writes share: a check in a read, a change applied once.

`plan` checks a change in a read-only transaction of the person and freezes the arguments
as given — only the fields the model sent, so a column's colour sent as null still removes
it after approval. `execute` applies the change in one transaction of the person with the
item's mark (`ActionItems`, Leo §8.4), so a repeated execution returns the stored outcome.
A refusal of the boards' rules reads to the model as a typed tool error.
"""

from collections.abc import Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import PlannedEffect, ToolError, ToolResult
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.kernel.errors import AppError
from shosai.features.tasks.application.board_access import owned_board
from shosai.features.tasks.application.boards import board_failure
from shosai.features.tasks.application.columns import not_found
from shosai.features.tasks.channels.agent_tool_errors import person, tool_error
from shosai.features.tasks.domain.boards import BoardRuleError
from shosai.features.tasks.infrastructure.board_records import BoardColumnRecord

type Check = Callable[[AsyncSession], Awaitable[None]]
type Effect[O: BaseModel] = Callable[[AsyncSession], Awaitable[O]]


def planned(args: BaseModel, target: str) -> PlannedEffect:
    """The checked arguments, as sent, as the agent keeps them until approval."""
    return PlannedEffect((target,), args.model_dump(mode="json", exclude_unset=True))


def refusal(error: BoardRuleError | AppError) -> ToolError:
    """A refusal of the boards' rules or of tasks as the model reads it."""
    return tool_error(board_failure(error) if isinstance(error, BoardRuleError) else error)


class BoardWork:
    """Checks and applies the person's board changes for Leo's tools."""

    def __init__(
        self, transactions: HomeTransactions, items: ActionItems, outbox: EventOutbox
    ) -> None:
        self.transactions = transactions
        self.outbox = outbox
        self._items = items

    async def check(self, context: ToolContext, read: Check) -> ToolError | None:
        """None when the change holds in a read of the person's boards; its refusal if not."""
        try:
            async with self.transactions.begin(person(context).scope(), read_only=True) as session:
                await read(session)
        except (BoardRuleError, AppError) as error:
            return refusal(error)
        return None

    async def once[O: BaseModel](
        self, context: ToolContext, item: tuple[str, str], change: tuple[type[O], Effect[O]]
    ) -> ToolResult[O]:
        """The change applied once for the item's key; the stored outcome on a repeat."""
        key, tool = item
        output, effect = change
        try:
            async with self.transactions.begin(person(context).scope()) as session:
                outcome = await self._items.once(
                    session, (key, tool, 1), output, lambda: effect(session)
                )
        except (BoardRuleError, AppError) as error:
            return ToolResult(error=refusal(error))
        return ToolResult(outcome)

    async def board_name(self, context: ToolContext, board_id: UUID) -> str:
        """The person's board's name; `not_found` raised as the board's error."""
        async with self.transactions.begin(person(context).scope(), read_only=True) as session:
            board = await owned_board(session, person(context).user_id, board_id)
        return board.name

    async def columns(
        self, context: ToolContext, board_id: UUID
    ) -> tuple[str, list[BoardColumnRecord]]:
        """The person's board's name and its columns, left to right."""
        async with self.transactions.begin(person(context).scope(), read_only=True) as session:
            return await columns_of(session, person(context).user_id, board_id)


async def columns_of(
    session: AsyncSession, viewer: UUID, board_id: UUID
) -> tuple[str, list[BoardColumnRecord]]:
    """The person's board's name and its columns, left to right; `board_not_found`."""
    board = await owned_board(session, viewer, board_id)
    found = await session.scalars(
        select(BoardColumnRecord)
        .where(BoardColumnRecord.board_id == board_id)
        .order_by(BoardColumnRecord.position)
    )
    return board.name, list(found)


def column_in(columns: list[BoardColumnRecord], column_id: UUID) -> BoardColumnRecord:
    """The board's column; `column_not_found` otherwise."""
    column = next((found for found in columns if found.id == column_id), None)
    if column is None:
        raise not_found()
    return column
