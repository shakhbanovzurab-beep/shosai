"""A turn's first transaction (Leo §5.2 step 4; §14 rule 1: commit before streaming).

Under its `Idempotency-Key` the transaction writes the question and the running run and
moves the thread's last activity; an untitled thread takes its title from the question. A
concurrent repeat of the key finds the outcome the first one stored and answers its run. A
run that was committed but could not be sent to a worker is ended `failed` at once, so
nothing waits for it.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import update

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import EffectKey, EffectLedger
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.domain.runs import Channel, RunFailure, RunStatus
from shosai.features.agent.domain.threads import MessageRole, title_from_question
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord
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


class TurnMade(BaseModel):
    """The run a turn's key made."""

    run_id: UUID


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
            session.add_all(
                [
                    AgentMessageRecord(
                        id=terms.question_id, created_at=now, thread_id=thread.id,
                        user_id=principal.user_id, run_id=terms.run_id,
                        role=MessageRole.USER.value, text=question,
                        tokens=estimate_tokens(question),
                    ),
                    AgentRunRecord(
                        id=terms.run_id, started_at=now, thread_id=thread.id,
                        user_id=principal.user_id, channel=Channel.WEB.value,
                        status=RunStatus.RUNNING.value, token_route=terms.token_route,
                    ),
                ]
            )  # fmt: skip
            thread.last_activity_at = now
            if thread.title is None:
                thread.title = title_from_question(question)
            await session.flush()
            return TurnMade(run_id=terms.run_id)

        done = await parts.effects.once(session, effect, TurnMade, write)
        return done.outcome


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
