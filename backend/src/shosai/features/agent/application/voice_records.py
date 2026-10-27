"""A voice exchange in the thread (ADR 0070, LV-D5): one run of channel `voice` per exchange.

The run's row is written when the exchange first calls a tool, so a card it proposes has its
run, or at the exchange's end when it called none. The end writes, in one transaction of the
person's home, the person's phrase as the question and Leo's words as the answer — stopped
when the person interrupted — with the steps, sources and cards of the exchange; the thread's
last activity moves, a first title comes from the phrase, and the completed turn is told
through the outbox as a text turn's is. A thread deleted meanwhile keeps nothing. Transcripts
longer than a question may be are cut to its limit.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from sqlalchemy import select, update

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.features.agent.application.run_end import millis
from shosai.features.agent.application.run_sources import kept
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.contracts.voice import VoiceExchange
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.domain.runs import Channel, RunStatus
from shosai.features.agent.domain.threads import (
    QUESTION_MAX,
    AnswerStatus,
    MessageRole,
    title_from_question,
)
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import (
    AgentMessageRecord,
    AgentThreadRecord,
)

RUN = AgentRunRecord
TICK: Final = timedelta(microseconds=1)


def voice_run(payload: TurnPayload, status: RunStatus) -> AgentRunRecord:
    """The exchange's run row."""
    return AgentRunRecord(
        id=payload.run_id, started_at=payload.started_at, thread_id=payload.thread_id,
        user_id=payload.user_id, channel=Channel.VOICE.value, language=payload.language,
        status=status.value, token_route=payload.token_route,
    )  # fmt: skip


async def open_voice_run(transactions: HomeTransactions, payload: TurnPayload) -> None:
    """Write the exchange's run before its first tool call."""
    async with transactions.begin(payload.scope()) as session:
        session.add(voice_run(payload, RunStatus.RUNNING))


@dataclass(frozen=True, slots=True)
class VoiceRecord:
    """The exchange as recorded: its terms, its work and whether its run is written."""

    payload: TurnPayload
    work: RunWork
    run_open: bool


async def record_exchange(
    writers: tuple[HomeTransactions, EventOutbox], record: VoiceRecord, exchange: VoiceExchange
) -> bool:
    """Write the exchange to its thread; False when the thread is gone or nothing was said."""
    transactions, outbox = writers
    payload, work = record.payload, record.work
    question, answer = exchange.question.strip()[:QUESTION_MAX], exchange.answer.strip()
    if not question and not answer and not record.run_open:
        return False
    async with transactions.begin(payload.scope()) as session:
        thread = await session.scalar(
            select(AgentThreadRecord)
            .where(AgentThreadRecord.id == payload.thread_id)
            .with_for_update()
        )
        status = RunStatus.COMPLETED if thread is not None else RunStatus.CANCELLED
        if record.run_open:
            await session.execute(
                update(RUN)
                .where(RUN.id == payload.run_id, RUN.started_at == payload.started_at)
                .values(status=status.value, ended_at=exchange.ended_at, tool_calls=len(work.steps))
            )
        else:
            row = voice_run(payload, status)
            row.ended_at, row.tool_calls = exchange.ended_at, len(work.steps)
            session.add(row)
        if thread is None:
            return False
        session.add_all(messages(thread, record, (question, answer), exchange))
        thread.last_activity_at = exchange.ended_at
        if thread.title is None and question:
            thread.title = title_from_question(question)
        completed = TurnCompleted(
            thread_id=payload.thread_id, run_id=payload.run_id, user_id=thread.user_id
        )
        await outbox.add(session, completed)
    return True


def messages(
    thread: AgentThreadRecord,
    record: VoiceRecord,
    said: tuple[str, str],
    exchange: VoiceExchange,
) -> list[AgentMessageRecord]:
    """The question, when the person said something, and Leo's answer."""
    payload, work = record.payload, record.work
    question, answer = said
    rows = []
    if question:
        rows.append(
            AgentMessageRecord(
                id=payload.question_id, created_at=exchange.started_at, thread_id=thread.id,
                user_id=thread.user_id, run_id=payload.run_id, role=MessageRole.USER.value,
                text=question, tokens=estimate_tokens(question), attachments=[],
            )
        )  # fmt: skip
    status = AnswerStatus.STOPPED if exchange.interrupted else AnswerStatus.DONE
    rows.append(
        AgentMessageRecord(
            id=payload.reply_id, created_at=answered_at(exchange), thread_id=thread.id,
            user_id=thread.user_id, run_id=payload.run_id, role=MessageRole.ASSISTANT.value,
            status=status.value, text=answer, steps=work.ordered_steps(),
            sources=kept(work, payload.language), tokens=estimate_tokens(answer),
            duration_ms=millis(exchange.ended_at - exchange.started_at),
            action_ids=list(work.cards), artifacts=list(work.artifacts),
        )
    )  # fmt: skip
    return rows


def answered_at(exchange: VoiceExchange) -> datetime:
    """The answer's moment: strictly after the question, whose moment is the exchange's start."""
    return max(exchange.ended_at, exchange.started_at + TICK)
