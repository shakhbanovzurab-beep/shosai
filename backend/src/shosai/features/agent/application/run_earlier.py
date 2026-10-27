"""What a paused run did before its card, read back for the epilogue (Leo §5.3 step 3; step 9a2).

The frame keeps references only, so the resumed run reads its own past from the database, as
its person. The model reads again the rounds the run kept at the pause — each model message
with its calls and each call's answer as it was read — and then the server note that tells, in
registered words, what became of the action. The run goes on with its answer so far, its steps
and sources, the rounds, calls and toolsets its row recorded, and the taint it had reached,
which the action recorded. Nothing is taken from the frame or the cache.
"""

from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.sources import SourceKind, SourceRef
from shosai.core.ai.requests import ChatMessage, Role, TextPart, ToolCall
from shosai.features.agent.application.history_text import said
from shosai.features.agent.application.run_context import text_message
from shosai.features.agent.application.run_work import EarlierWork, Step
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.threads import MessageRole
from shosai.features.agent.infrastructure.run_records import AgentActionRecord, AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord

MESSAGE = AgentMessageRecord
# Строки прогона, которые модель читает снова: раунды, ответы инструментов и заметки сервера.
RESUMED_ROLES = (MessageRole.ASSISTANT.value, MessageRole.TOOL.value, MessageRole.SERVER.value)


async def earlier_work(session: AsyncSession, payload: TurnPayload, action_id: UUID) -> EarlierWork:
    """The run's past as its person reads it."""
    run = await session.scalar(
        select(AgentRunRecord).where(
            AgentRunRecord.id == payload.run_id, AgentRunRecord.user_id == payload.user_id
        )
    )
    action = await session.scalar(
        select(AgentActionRecord).where(
            AgentActionRecord.id == action_id, AgentActionRecord.user_id == payload.user_id
        )
    )
    rows = list(
        await session.scalars(
            select(MESSAGE)
            .where(
                MESSAGE.thread_id == payload.thread_id,
                MESSAGE.user_id == payload.user_id,
                MESSAGE.run_id == payload.run_id,
                MESSAGE.role.in_(RESUMED_ROLES),
            )
            .order_by(MESSAGE.created_at, MESSAGE.id)
        )
    )
    messages = tuple(
        message for row in rows if row.id != payload.reply_id and (message := read_again(row))
    )
    reply = next((row for row in rows if row.id == payload.reply_id), None)
    return replace(
        answer_so_far(reply), messages=messages, **run_counts(run), **reached_taint(action)
    )


def answer_so_far(reply: AgentMessageRecord | None) -> EarlierWork:
    """The answer the run wrote before its card, with its steps and sources."""
    if reply is None:
        return EarlierWork()
    return EarlierWork(
        text=reply.text,
        cards=tuple(reply.action_ids),
        artifacts=tuple(reply.artifacts),
        steps=tuple(step_of(each) for each in reply.steps),
        sources=tuple(source_of(each) for each in reply.sources),
    )


def run_counts(run: AgentRunRecord | None) -> dict[str, Any]:
    """The rounds, calls and toolsets the run's row recorded before its card."""
    if run is None:
        return {}
    return {"rounds": run.rounds, "calls": run.tool_calls, "routing": dict(run.routing)}


def reached_taint(action: AgentActionRecord | None) -> dict[str, Any]:
    """The taint the run had reached when it proposed the action, and its labels."""
    if action is None:
        return {}
    return {"taint": Taint(action.taint), "taint_sources": tuple(action.taint_sources)}


def read_again(row: AgentMessageRecord) -> ChatMessage | None:
    """A row of the run as the model reads it again; None for a row it never read."""
    if row.role == MessageRole.TOOL.value and row.tool_call_id is not None:
        content = str((row.digest or {}).get("text", ""))
        return ChatMessage(Role.TOOL, (TextPart(content),), tool_call_id=row.tool_call_id)
    if row.role == MessageRole.ASSISTANT.value and row.tool_calls is not None:
        calls = tuple(
            ToolCall(str(call["id"]), str(call["name"]), str(call["arguments"]))
            for call in row.tool_calls
        )
        parts = (TextPart(row.text),) if row.text else ()
        return ChatMessage(Role.ASSISTANT, parts, tool_calls=calls)
    if row.role == MessageRole.SERVER.value:
        # Заметка сервера — без вложений: граница обёртки ей не нужна.
        return text_message(Role.USER, said(row.role, row.text, row.digest, row.sources, ""))
    return None


def step_of(stored: dict[str, Any]) -> Step:
    """A step back from the answer's row."""
    seq = int(str(stored["id"]).removeprefix("step-"))
    code = stored.get("code")
    return Step(
        seq,
        str(stored["activity"]),
        None if stored.get("detail") is None else str(stored["detail"]),
        str(stored["status"]),
        int(stored.get("duration_ms") or 0),
        None if code is None else str(code),
    )


def source_of(stored: dict[str, Any]) -> SourceRef:
    """A source back from the answer's row: what it is and the space it belongs to."""
    org = stored.get("org_id")
    locator = stored.get("locator")
    return SourceRef(
        SourceKind(str(stored["kind"])),
        str(stored["id"]),
        str(stored["title"]),
        None if org is None else UUID(str(org)),
        None if locator is None else str(locator),
        str(stored.get("quote") or ""),
    )
