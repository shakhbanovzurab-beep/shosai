"""A turn's input for the model, first cut (Leo §7.3; the full context builder is step 5b).

The policy and the turn's language and length come first and never change within a thread's
day, then the newest messages that fit the recent segment's 5 000 tokens, oldest first, then
the question. A failed answer's text is left out; tool rounds do not exist yet. The thread is
read as the person, so a deleted thread ends the run before the model is asked, and so does a
run the sweep ended while it waited for a worker.
"""

from typing import Final
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import recent_window
from shosai.features.agent.domain.runs import RunStatus
from shosai.features.agent.domain.threads import AnswerStatus, MessageRole
from shosai.features.agent.infrastructure.prompts import POLICY, turn_instructions
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import (
    AgentMessageRecord,
    AgentThreadRecord,
)

MESSAGE = AgentMessageRecord
MAX_OUTPUT_TOKENS: Final = 4_096
# Строк читается с запасом: окно режет их по токенам, редкий тред упрётся в это число раньше.
HISTORY_ROWS: Final = 60
ROLES: Final = {MessageRole.USER.value: Role.USER, MessageRole.ASSISTANT.value: Role.ASSISTANT}


class ThreadGoneError(Exception):
    """The run's thread was deleted after the turn was admitted."""


class RunOverError(Exception):
    """The run ended before its worker took it: the sweep found it lost meanwhile."""


def text_message(role: Role, text: str) -> ChatMessage:
    """One message of plain text."""
    return ChatMessage(role=role, parts=(TextPart(text),))


async def turn_request(session: AsyncSession, payload: TurnPayload) -> ChatRequest:
    """The request for the model, read in the person's transaction."""
    user_id = _person(payload)
    status = await session.scalar(
        select(AgentRunRecord.status).where(
            AgentRunRecord.id == payload.run_id, AgentRunRecord.started_at == payload.started_at
        )
    )
    if status != RunStatus.RUNNING.value:
        raise RunOverError
    thread = await session.scalar(
        select(AgentThreadRecord).where(
            AgentThreadRecord.id == payload.thread_id, AgentThreadRecord.user_id == user_id
        )
    )
    if thread is None:
        raise ThreadGoneError
    rows = (
        await session.execute(
            select(MESSAGE.id, MESSAGE.role, MESSAGE.text, MESSAGE.tokens)
            .where(
                MESSAGE.thread_id == thread.id,
                MESSAGE.user_id == user_id,
                MESSAGE.created_at >= thread.created_at,
                MESSAGE.role.in_(tuple(ROLES)),
                or_(MESSAGE.status.is_(None), MESSAGE.status != AnswerStatus.FAILED.value),
            )
            .order_by(MESSAGE.created_at.desc(), MESSAGE.id.desc())
            .limit(HISTORY_ROWS)
        )
    ).all()
    question = next((row.text for row in rows if row.id == payload.question_id), None)
    if question is None:
        raise ThreadGoneError
    history = [row for row in rows if row.id != payload.question_id]
    kept = history[: recent_window([row.tokens for row in history])]
    system = f"{POLICY}\n\n{turn_instructions(payload.language, payload.length)}"
    return ChatRequest(
        messages=(
            text_message(Role.SYSTEM, system),
            *(text_message(ROLES[row.role], row.text) for row in reversed(kept)),
            text_message(Role.USER, question),
        ),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )


def _person(payload: TurnPayload) -> UUID:
    if payload.user_id is None:
        message = "ход Leo идёт от имени человека"
        raise ValueError(message)
    return payload.user_id
