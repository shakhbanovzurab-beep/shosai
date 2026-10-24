"""A run's end in the database: one transaction the worker or the sweep wins (Leo §5.2 step 11).

The run moves from `running` with a condition, so of the run's worker and the lost-run sweep
exactly one records an end. The answer is kept with the text the model wrote and the steps the
person saw, after the rounds that led to it — each model message with its calls and each call's
answer as the model read it, for the run's record, never for later turns' context; a
regenerated or edited question's earlier answers and rounds give way to it. The thread's last
activity moves, and a completed turn is told through the outbox. A thread deleted meanwhile
turns the end into `cancelled` and keeps nothing.
"""

from datetime import datetime, timedelta
from typing import Any, Final

from sqlalchemy import delete, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.ids import new_id
from shosai.features.agent.application.run_telemetry import TIER, TurnTimes, micro_usd
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.domain.endings import Ending, cancelled
from shosai.features.agent.domain.runs import RunStatus
from shosai.features.agent.domain.threads import AnswerStatus, MessageRole, TurnKind
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import (
    AgentMessageRecord,
    AgentThreadRecord,
)
from shosai.features.agent.infrastructure.turn_graph import ModelAnswer

RUN = AgentRunRecord
# Ответ и раунды хода: их заменяет новый ответ на тот же вопрос.
ANSWER_ROLES: Final = (MessageRole.ASSISTANT.value, MessageRole.TOOL.value)
TICK: Final = timedelta(microseconds=1)


async def record_end(
    writers: tuple[HomeTransactions, EventOutbox],
    payload: TurnPayload,
    result: tuple[Ending, str, ModelAnswer | None],
    clocked: tuple[TurnTimes, datetime],
    work: RunWork,
) -> Ending | None:
    """The final transaction; the ending it recorded, or None when the sweep won."""
    transactions, outbox = writers
    ending, text, answer = result
    times, now = clocked
    async with transactions.begin(payload.scope()) as session:
        thread = await session.scalar(
            select(AgentThreadRecord)
            .where(AgentThreadRecord.id == payload.thread_id)
            .with_for_update()
        )
        if thread is None:
            ending = cancelled()
        won = await session.scalar(
            update(RUN)
            .where(
                RUN.id == payload.run_id,
                RUN.started_at == payload.started_at,
                RUN.status == RunStatus.RUNNING.value,
            )
            .values(ended_at=now, **telemetry(payload, (ending, answer), (times, work), now))
            .returning(RUN.id)
        )
        if won is None:
            return None
        if thread is not None:
            if ending.keeps(text) and ending.answer is not None:
                await replace_answers(session, payload)
                session.add_all(round_rows(thread, payload, work, now))
                session.add(
                    AgentMessageRecord(
                        id=payload.reply_id, created_at=now, thread_id=thread.id,
                        user_id=thread.user_id, run_id=payload.run_id,
                        role=MessageRole.ASSISTANT.value, status=ending.answer.value,
                        text=text, steps=work.ordered_steps(), tokens=estimate_tokens(text),
                        duration_ms=millis(now - payload.started_at),
                    )
                )  # fmt: skip
            thread.last_activity_at = now
            if ending.status is RunStatus.COMPLETED:
                completed = TurnCompleted(
                    thread_id=payload.thread_id, run_id=payload.run_id, user_id=thread.user_id
                )
                await outbox.add(session, completed)
    return ending


async def replace_answers(session: AsyncSession, payload: TurnPayload) -> None:
    """A regenerated or edited question's earlier answers give way to the new one."""
    if payload.kind is TurnKind.NEW:
        return
    question = await session.scalar(
        select(AgentMessageRecord).where(
            AgentMessageRecord.id == payload.question_id,
            AgentMessageRecord.thread_id == payload.thread_id,
        )
    )
    if question is None:
        return
    after = tuple_(AgentMessageRecord.created_at, AgentMessageRecord.id) > tuple_(
        question.created_at, question.id
    )
    await session.execute(
        delete(AgentMessageRecord).where(
            AgentMessageRecord.thread_id == payload.thread_id,
            AgentMessageRecord.created_at >= question.created_at,
            AgentMessageRecord.role.in_(ANSWER_ROLES),
            after,
        )
    )


def round_rows(
    thread: AgentThreadRecord, payload: TurnPayload, work: RunWork, now: datetime
) -> list[AgentMessageRecord]:
    """The run's rounds as rows before its answer: each model message, then its calls'
    answers, a microsecond apart so the thread's order holds."""
    rows: list[AgentMessageRecord] = []
    moment = payload.started_at
    for each in work.rounds:
        moment = min(max(each.at, moment + TICK), now - TICK)
        calls = [{"id": c.call_id, "name": c.name, "arguments": c.arguments} for c in each.calls]
        rows.append(
            AgentMessageRecord(
                id=new_id(), created_at=moment, thread_id=thread.id, user_id=thread.user_id,
                run_id=payload.run_id, role=MessageRole.ASSISTANT.value,
                status=AnswerStatus.DONE.value, text=each.text, tool_calls=calls,
                tokens=estimate_tokens(each.text),
            )
        )  # fmt: skip
        for answer in each.answers:
            moment += TICK
            rows.append(
                AgentMessageRecord(
                    id=new_id(), created_at=moment, thread_id=thread.id,
                    user_id=thread.user_id, run_id=payload.run_id, role=MessageRole.TOOL.value,
                    tool_call_id=answer.call_id, tool_name=answer.tool,
                    digest={"text": answer.content}, result_id=answer.result_id,
                    tokens=estimate_tokens(answer.content),
                )
            )  # fmt: skip
    return rows


def millis(delta: timedelta) -> int:
    """Milliseconds of a time span."""
    return int(delta.total_seconds() * 1000)


def telemetry(
    payload: TurnPayload,
    result: tuple[Ending, ModelAnswer | None],
    done: tuple[TurnTimes, RunWork],
    now: datetime,
) -> dict[str, Any]:
    """The run row's end: status and code, the model and its numbers, the tools, the times."""
    ending, answer = result
    times, work = done
    usage = answer.usage if answer is not None else None
    first = times.first_word(payload.started_at, answer)
    return {
        "status": ending.status.value,
        "outcome_code": ending.code,
        "model": answer.model if answer is not None else None,
        "tier": TIER,
        "token_route": payload.token_route,
        "rounds": len(work.answers),
        "tool_calls": work.tool_calls,
        "routing": work.offer.routing() if work.offer is not None else {},
        "input_tokens": usage.input_tokens if usage is not None else 0,
        "cached_tokens": usage.cached_tokens if usage is not None else 0,
        "output_tokens": usage.output_tokens if usage is not None else 0,
        "cost_micro_usd": micro_usd(answer),
        "ttft_ms": None if first is None else millis(first),
        "overhead_ms": millis(times.overhead(payload.started_at, now)),
        "duration_ms": millis(now - payload.started_at),
    }
