"""An approved egress call's result, read back into its resumed run (Leo §7.4; agent step 13b).

The run proposed the call as a card and told the model it waits. Once the call has run, the
epilogue reads its kept result through the run's own reader — its sources numbered among the
run's, its text wrapped with its tool's label, a digest of one over budget — and that read
replaces the waiting answer, in the model's conversation and in the run's row of it, so a later
resume of the same run reads the result again. A result whose tool is gone since, or whose
output no longer fits it, is left out: the server note still says what became of the call.
"""

import json
from dataclasses import dataclass, replace
from typing import Final
from uuid import UUID

import structlog
from pydantic import JsonValue, ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolResult
from shosai.core.agent_tools.sources import SourceRef
from shosai.core.agent_tools.spec import ToolEffect
from shosai.core.ai.requests import ChatMessage, Role, TextPart
from shosai.core.db.transactions import HomeTransactions
from shosai.features.agent.application.action_rows import items_of
from shosai.features.agent.application.egress_calls import CALL_ID, OUTPUT, SOURCES
from shosai.features.agent.application.run_earlier import source_of
from shosai.features.agent.application.run_sources import listed
from shosai.features.agent.application.run_work import EarlierWork, RunWork
from shosai.features.agent.application.tool_offer import TurnOffer
from shosai.features.agent.application.tool_read_back import ResultReader
from shosai.features.agent.application.turn_task import Emitter, TurnPayload
from shosai.features.agent.domain.action_items import ItemState
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.domain.runs import TURN_DEADLINE
from shosai.features.agent.domain.stream import EventKind
from shosai.features.agent.domain.threads import MessageRole
from shosai.features.agent.infrastructure.run_records import AgentActionRecord
from shosai.features.agent.infrastructure.thread_records import (
    AgentMessageRecord,
    AgentToolResultRecord,
)

MESSAGE: Final = AgentMessageRecord
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class KeptCall:
    """An approved egress call that ran: the model's call, its tool and what it returned."""

    call_id: str
    tool: str
    output: dict[str, JsonValue]
    sources: tuple[SourceRef, ...]


async def kept_call(
    session: AsyncSession, payload: TurnPayload, action_id: UUID
) -> KeptCall | None:
    """The action's egress call with its kept result, as its person reads them; None for any
    other action, or one whose call did not succeed."""
    action = await session.scalar(
        select(AgentActionRecord).where(
            AgentActionRecord.id == action_id, AgentActionRecord.user_id == payload.user_id
        )
    )
    if action is None:
        return None
    item = items_of(action)[0]
    egress = item.effect == ToolEffect.EGRESS.value and item.state is ItemState.SUCCEEDED
    if not egress or item.result is None:
        return None
    row = await session.scalar(
        select(AgentToolResultRecord).where(
            AgentToolResultRecord.id == UUID(item.result),
            AgentToolResultRecord.user_id == payload.user_id,
        )
    )
    if row is None:
        return None
    kept = json.loads(str(row.payload.get("json") or "{}"))
    return KeptCall(
        call_id=str(item.plan.get(CALL_ID) or ""),
        tool=item.tool,
        output=dict(kept.get(OUTPUT) or {}),
        sources=tuple(source_of(each) for each in kept.get(SOURCES) or []),
    )


def answered(messages: tuple[ChatMessage, ...], call_id: str, text: str) -> tuple[ChatMessage, ...]:
    """The conversation with the call's waiting answer replaced by its result."""
    return tuple(
        replace(message, parts=(TextPart(text),))
        if message.role is Role.TOOL and message.tool_call_id == call_id
        else message
        for message in messages
    )


class EgressAnswers:
    """Puts an approved call's result in place of its waiting answer, for one resumed run."""

    def __init__(
        self,
        parts: tuple[HomeTransactions, ResultReader],
        run: tuple[TurnPayload, RunWork, Emitter],
    ) -> None:
        self._transactions, self._reader = parts
        self._payload, self._work, self._emitter = run

    async def fold(self, earlier: EarlierWork, offer: TurnOffer, kept: KeptCall) -> EarlierWork:
        """The run's past with the result as the call's answer, kept in the call's row."""
        offered = offer.kept_from(kept.tool)
        if offered is None:
            return earlier
        try:
            output = offered.spec.output.model_validate(kept.output)
        except ValidationError:
            log.exception("Результат одобренного вызова не читается", tool=kept.tool)
            return earlier
        payload = self._payload
        context = ToolContext(
            payload.scope(), payload.run_id, payload.started_at + TURN_DEADLINE, self._work.taint
        )
        read = await self._reader.read(
            offer, offered, ToolResult(output, sources=kept.sources), context
        )
        async with self._transactions.begin(payload.scope()) as session:
            await session.execute(
                update(MESSAGE)
                .where(
                    MESSAGE.run_id == payload.run_id,
                    MESSAGE.user_id == payload.user_id,
                    MESSAGE.role == MessageRole.TOOL.value,
                    MESSAGE.tool_call_id == kept.call_id,
                )
                .values(
                    digest={"text": read.text}, result_id=read.result_id,
                    tokens=estimate_tokens(read.text),
                )
            )  # fmt: skip
        if read.new_sources:
            sources = listed(self._work, payload.language)
            await self._emitter.emit(EventKind.SOURCES, {"sources": list(sources)})
        return replace(earlier, messages=answered(earlier.messages, kept.call_id, read.text))
