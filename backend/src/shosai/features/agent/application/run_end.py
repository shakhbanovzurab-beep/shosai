"""A run's end in the database: one transaction the worker or the sweep wins (Leo §5.2 step 11).

The run moves from `running` with a condition, so of the run's worker and the lost-run sweep
exactly one records an end. The answer is kept with the text the model wrote, the thread's
last activity moves, and a completed turn is told through the outbox. A thread deleted
meanwhile turns the end into `cancelled` and keeps nothing.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.domain.endings import Ending, cancelled
from shosai.features.agent.domain.runs import RunStatus
from shosai.features.agent.domain.threads import MessageRole
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import (
    AgentMessageRecord,
    AgentThreadRecord,
)
from shosai.features.agent.infrastructure.turn_graph import ModelAnswer

RUN = AgentRunRecord


async def record_end(
    writers: tuple[HomeTransactions, EventOutbox],
    payload: TurnPayload,
    result: tuple[Ending, str, ModelAnswer | None],
    now: datetime,
) -> Ending | None:
    """The final transaction; the ending it recorded, or None when the sweep won."""
    transactions, outbox = writers
    ending, text, answer = result
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
            .values(ended_at=now, **telemetry(payload, ending, answer, now))
            .returning(RUN.id)
        )
        if won is None:
            return None
        if thread is not None:
            if ending.keeps(text) and ending.answer is not None:
                session.add(
                    AgentMessageRecord(
                        id=payload.reply_id, created_at=now, thread_id=thread.id,
                        user_id=thread.user_id, run_id=payload.run_id,
                        role=MessageRole.ASSISTANT.value, status=ending.answer.value,
                        text=text, tokens=estimate_tokens(text),
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


def millis(delta: timedelta) -> int:
    """Milliseconds of a time span."""
    return int(delta.total_seconds() * 1000)


def telemetry(
    payload: TurnPayload, ending: Ending, answer: ModelAnswer | None, now: datetime
) -> dict[str, Any]:
    """The run row's end: status and code, the model's numbers, the time it took."""
    usage = answer.usage if answer is not None else None
    return {
        "status": ending.status.value,
        "outcome_code": ending.code,
        "tier": "standard",
        "token_route": payload.token_route,
        "rounds": 1 if answer is not None else 0,
        "input_tokens": usage.input_tokens if usage is not None else 0,
        "cached_tokens": usage.cached_tokens if usage is not None else 0,
        "output_tokens": usage.output_tokens if usage is not None else 0,
        "ttft_ms": answer.first_token_ms if answer is not None else None,
        "duration_ms": millis(now - payload.started_at),
    }
