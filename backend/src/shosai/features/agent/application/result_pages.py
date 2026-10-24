"""Whole tool results, kept for the model to page through (Leo §7.3, ADR 0068 AG-D3; step 6).

A result longer than its tool's budget enters the context as a digest naming its
`result_ref`; the whole of it is kept in `agent_tool_results` and read by `core.read_result` a
page at a time, for 30 days. A result may hold anything the person could read through any of
their workspaces — a colleague's meeting shared into one among it — so it is kept with every
workspace they are in, and every read re-checks them: once the person has left any of them,
the result is refused and nothing it may hold is paged out again (re-asking the tool reads
what they may read now). A ref that is not the person's, or older than 30 days, is not found.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import select

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.infrastructure.thread_records import AgentToolResultRecord
from shosai.features.workspaces.contracts import MEMBERSHIP_READER

RESULT = AgentToolResultRecord
READABLE_FOR: Final = timedelta(days=30)
# Страница — до 6 000 байт: с экранированием в JSON остаётся в бюджете core.read_result.
PAGE_BYTES: Final = 6_000


@dataclass(frozen=True, slots=True)
class ResultPage:
    """A page of a kept result, the cursor of the next and the tool whose result it is."""

    text: str
    next_cursor: int | None
    tool: str


class ResultPages:
    """Keeps whole results and pages them back to the model."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._clock = clock

    async def keep(self, context: ToolContext, tool: str, payload: str) -> UUID:
        """Store a whole result with the person's workspaces now; its ref."""
        user_id = person(context)
        result_id = new_id()
        async with self._transactions.begin(context.scope) as session:
            memberships = await self._ports.get(MEMBERSHIP_READER).active(session, user_id)
            spaces = frozenset(membership.org_id for membership in memberships)
            session.add(
                RESULT(
                    id=result_id, created_at=self._clock(), user_id=user_id,
                    run_id=context.run_id, tool_name=tool, payload={"json": payload},
                    spaces=sorted(spaces), tokens=estimate_tokens(payload),
                )
            )  # fmt: skip
        return result_id

    async def page(self, context: ToolContext, ref: str, cursor: int) -> ResultPage | ToolErrorCode:
        """A page of the person's result; `not_found` for a ref that is not theirs or too old,
        `forbidden` for one from a space they left."""
        try:
            result_id = UUID(ref)
        except ValueError:
            return ToolErrorCode.NOT_FOUND
        user_id = person(context)
        async with self._transactions.begin(context.scope, read_only=True) as session:
            row = (
                await session.execute(
                    select(RESULT.payload, RESULT.spaces, RESULT.tool_name).where(
                        RESULT.id == result_id,
                        RESULT.user_id == user_id,
                        RESULT.created_at >= self._clock() - READABLE_FOR,
                    )
                )
            ).one_or_none()
            if row is None:
                return ToolErrorCode.NOT_FOUND
            memberships = await self._ports.get(MEMBERSHIP_READER).active(session, user_id)
        active = {membership.org_id for membership in memberships}
        if not set(row.spaces) <= active:
            return ToolErrorCode.FORBIDDEN
        text = str(row.payload.get("json", ""))
        chunk = text[cursor : cursor + PAGE_BYTES]
        # Символ — от одного до четырёх байт: страница режется по байтам на границе символа.
        chunk = chunk.encode()[:PAGE_BYTES].decode(errors="ignore")
        end = cursor + len(chunk)
        return ResultPage(chunk, end if end < len(text) else None, row.tool_name)


def person(context: ToolContext) -> UUID:
    """The person a tool call acts for."""
    if context.scope.user_id is None:
        message = "инструмент Leo вызывается от имени человека"
        raise ValueError(message)
    return context.scope.user_id
