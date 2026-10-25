"""A turn's first transaction (Leo §5.2 step 4; §14 rule 1: commit before streaming).

Under its `Idempotency-Key` the transaction writes the question and the running run and
moves the thread's last activity; an untitled thread takes its title from the question. The
thread's runs paused on a card close (`new_turn`): the conversation went on, so no epilogue
follows, while their cards stay decidable. A concurrent repeat of the key finds the outcome
the first one stored and answers its run. A run that was committed but could not be sent to a
worker is ended `failed` at once, so nothing waits for it.
"""

from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import EffectKey, EffectLedger
from shosai.core.kernel.errors import AppError
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.features.agent.application.run_close import close_for_new_turn
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.domain.runs import Channel, RunFailure, RunStatus
from shosai.features.agent.domain.threads import (
    MessageRole,
    ThreadRuleError,
    TurnKind,
    check_replacement,
    title_from_question,
)
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.thread_records import (
    AgentMessageRecord,
    AgentThreadRecord,
)
from shosai.features.agent.infrastructure.turn_saver import TurnSaver
from shosai.features.identity.contracts import Principal


class TurnQueue(Protocol):
    """Sends an admitted turn to the `agent` queue."""

    async def send(self, task: TaskDeclaration[TurnPayload], payload: TurnPayload) -> str:
        """Queue the run; its task id."""
        ...


@dataclass(frozen=True, slots=True)
class TurnParts:
    """What admitting a turn works with in the API."""

    transactions: HomeTransactions
    ports: PortDirectory
    effects: EffectLedger
    limiter: RateLimiter
    tasks: TurnQueue
    run_log: RunLog
    leases: ThreadLeases
    fleet: Fleet
    threads: Threads
    frames: TurnSaver


class TurnMade(BaseModel):
    """The run a turn's key made, and the paused runs it closed."""

    run_id: UUID
    closed: tuple[UUID, ...] = ()


async def commit_turn(
    parts: TurnParts, principal: Principal, terms: TurnPayload, asked: tuple[EffectKey, str]
) -> TurnMade:
    """Write the question and the run once per key; the run the key made."""
    effect, question = asked
    async with parts.transactions.begin(principal.scope()) as session:

        async def write() -> TurnMade:
            thread = await parts.threads.visible_thread(
                session, principal.user_id, terms.thread_id, lock=True
            )
            now = terms.started_at
            await ask(session, thread, terms, question)
            session.add(
                AgentRunRecord(
                    id=terms.run_id, started_at=now, thread_id=thread.id,
                    user_id=principal.user_id, channel=Channel.WEB.value,
                    status=RunStatus.RUNNING.value, token_route=terms.token_route,
                )
            )  # fmt: skip
            closed = await close_for_new_turn(session, thread.id, now)
            thread.last_activity_at = now
            if thread.title is None:
                thread.title = title_from_question(question)
            await session.flush()
            return TurnMade(run_id=terms.run_id, closed=tuple(closed))

        done = await parts.effects.once(session, effect, TurnMade, write)
        return done.outcome


async def ask(
    session: AsyncSession, thread: AgentThreadRecord, terms: TurnPayload, question: str
) -> None:
    """Write a new question, or answer the thread's last one again — rewritten for an edit;
    any other question is 409 `not_last_question`."""
    last = await session.scalar(
        select(AgentMessageRecord)
        .where(
            AgentMessageRecord.thread_id == thread.id,
            AgentMessageRecord.created_at >= thread.created_at,
            AgentMessageRecord.role == MessageRole.USER.value,
        )
        .order_by(AgentMessageRecord.created_at.desc(), AgentMessageRecord.id.desc())
        .limit(1)
    )
    named = None if terms.kind is TurnKind.NEW else terms.question_id
    try:
        check_replacement(terms.kind, named, last.id if last is not None else None)
    except ThreadRuleError as error:
        raise AppError(error.rule.value, HTTPStatus.CONFLICT) from error
    if last is not None and terms.kind is TurnKind.EDIT:
        last.text, last.tokens, last.run_id = question, estimate_tokens(question), terms.run_id
        return
    if terms.kind is TurnKind.NEW:
        session.add(
            AgentMessageRecord(
                id=terms.question_id, created_at=terms.started_at, thread_id=thread.id,
                user_id=thread.user_id, run_id=terms.run_id, role=MessageRole.USER.value,
                text=question, tokens=estimate_tokens(question),
            )
        )  # fmt: skip


async def abandon_turn(transactions: HomeTransactions, terms: TurnPayload, now: datetime) -> None:
    """End a committed run that never reached a worker."""
    async with transactions.begin(terms.scope()) as session:
        await session.execute(
            update(AgentRunRecord)
            .where(
                AgentRunRecord.id == terms.run_id,
                AgentRunRecord.started_at == terms.started_at,
                AgentRunRecord.status == RunStatus.RUNNING.value,
            )
            .values(
                status=RunStatus.FAILED.value, outcome_code=RunFailure.FAILED.value, ended_at=now
            )
        )
