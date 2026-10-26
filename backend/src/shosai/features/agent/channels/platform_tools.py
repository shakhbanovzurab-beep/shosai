"""The operator's `platform` toolset bound to its reads (ADR 0068 AG-D5; agent step 16).

What platform services already serve their operator is read for Leo in the admin panel (see
`platform_reads`). No tool reads a person's content or changes anything, and each refuses any
caller but the platform operator, whatever offered it. Other owners add their aggregates
through their contracts.
"""

from typing import Any

from pydantic import BaseModel

from shosai.core.agent_tools.bindings import AgentTool, ReadTool, RunHandler
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.agent_tools.spec import ToolSpec
from shosai.features.agent.channels.platform_reads import PlatformReads
from shosai.features.agent.channels.platform_specs import (
    ACCOUNTS,
    ANSWER_RATINGS,
    OPENROUTER_BALANCE,
    PLANS,
    PROMO_CODES,
    SPEND_DAILY,
    SPEND_FORECAST,
    SPEND_SUMMARY,
)
from shosai.features.agent.domain.operator import is_operator


def operator_only[I: BaseModel, O: BaseModel](run: RunHandler[I, O]) -> RunHandler[I, O]:
    """The handler, for the operator alone: anyone else is refused, whatever offered it."""

    async def guarded(arguments: I, context: ToolContext) -> ToolResult[O]:
        if not is_operator(context.scope.user_id):
            return ToolResult.failed(ToolErrorCode.FORBIDDEN)
        return await run(arguments, context)

    return guarded


def platform_tools(reads: PlatformReads) -> tuple[AgentTool, ...]:
    """The toolset bound to the operator's reads, each for the operator alone."""
    handlers: tuple[tuple[ToolSpec[Any, Any], RunHandler[Any, Any]], ...] = (
        (SPEND_SUMMARY, reads.spend_summary), (SPEND_DAILY, reads.spend_daily),
        (SPEND_FORECAST, reads.spend_forecast), (OPENROUTER_BALANCE, reads.openrouter_balance),
        (ANSWER_RATINGS, reads.answer_ratings), (PLANS, reads.plans),
        (PROMO_CODES, reads.promo_codes), (ACCOUNTS, reads.accounts),
    )  # fmt: skip
    return tuple(ReadTool(spec, operator_only(run)) for spec, run in handlers)
