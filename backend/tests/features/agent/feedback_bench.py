"""Ratings under answers over the slot's homes, with identity's consent and profile as the test
sets them (agent step 11a).

A turn is written straight into the thread as a run leaves it: the question, a round with its
call and the digest the model read, the answer with its sources, and the run's row.
"""

import uuid
from collections.abc import AsyncIterator, Collection, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pytest_asyncio
from prometheus_client import CollectorRegistry
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.config.roles import ProcessRole
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.case_care import CasePurge
from shosai.features.agent.application.feedback import Feedback
from shosai.features.agent.application.history import History
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.channels.http.feedback import build_feedback_router
from shosai.features.agent.channels.http.threads import build_threads_router
from shosai.features.agent.infrastructure.feedback_metrics import FeedbackMetrics
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord
from shosai.features.identity.contracts import (
    ACCOUNT_PROFILE_READER,
    AUTHENTICATOR,
    CONSENT_READER,
    AccountProfile,
)
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from shosai.features.workspaces.infrastructure.membership_reader import MembershipDirectory
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.agent.thread_bench import HOME, TestClock, ThreadBench
from tests.features.billing.people_bench import BearerOfTheTest
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

TICK = timedelta(milliseconds=1)


@dataclass
class People:
    """Identity as the test sets it: who lets their conversations improve the models, and
    each person's name."""

    improving: set[uuid.UUID] = field(default_factory=set)
    names_by_person: dict[uuid.UUID, str] = field(default_factory=dict)

    async def cross_border(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Consent given."""
        del session, user_id
        return True

    async def improve_models(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Whether the test let the person's conversations improve the models."""
        del session
        return user_id in self.improving

    async def profile(self, session: AsyncSession, user_id: uuid.UUID) -> AccountProfile | None:
        """The person's name in English."""
        del session
        return AccountProfile(self.names_by_person.get(user_id, "Person"), "en", None)

    async def names(
        self, session: AsyncSession, user_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, str]:
        """The names the test set."""
        del session
        return {
            user: self.names_by_person[user] for user in user_ids if user in self.names_by_person
        }


@dataclass(frozen=True, slots=True)
class RunFacts:
    """What the run row and the answer keep: the model, tier, language, toolsets, sources."""

    model: str | None = None
    tier: str | None = None
    language: str | None = None
    routing: dict[str, list[str]] = field(default_factory=dict)
    sources: list[dict[str, str | None]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class FeedbackBench(ThreadBench):
    """The thread and rating routes, identity's answers and the counters."""

    people: People = field(default_factory=People)
    registry: CollectorRegistry = field(default_factory=CollectorRegistry)

    async def turn(
        self,
        person: uuid.UUID,
        thread: str,
        words: tuple[str, str, str],
        made: RunFacts | None = None,
    ) -> tuple[str, str]:
        """A finished turn: the question, a round reading the digest, the answer; the
        answer's and the question's ids."""
        question, digest, answer = words
        facts = made or RunFacts()
        run_id, at, answer_id = uuid.uuid4(), self.clock.now, uuid.uuid4()
        asked = await self.message(person, thread, "user", at, question)
        call = {"id": "c1", "name": "notes__search", "arguments": {"q": question}}
        rows = [
            AgentRunRecord(
                id=run_id, started_at=at, thread_id=uuid.UUID(thread), user_id=person,
                channel="web", status="completed", ended_at=at + 5 * TICK, model=facts.model,
                tier=facts.tier, language=facts.language, routing=facts.routing,
            ),
            self._row((person, thread, run_id), at + TICK, role="assistant", status="done",
                      text="Searching.", tool_calls=[call]),
            self._row((person, thread, run_id), at + 2 * TICK, role="tool", tool_call_id="c1",
                      tool_name="notes.search", digest={"text": digest}),
            self._row((person, thread, run_id), at + 3 * TICK, id=answer_id, role="assistant",
                      status="done", text=answer, sources=facts.sources),
        ]  # fmt: skip
        async with self.homes.transactions.begin(TenancyScope(HOME, person)) as session:
            session.add_all(rows)
        self.clock.advance(timedelta(seconds=1))
        return str(answer_id), asked

    @staticmethod
    def _row(
        where: tuple[uuid.UUID, str, uuid.UUID], at: datetime, **fields: object
    ) -> AgentMessageRecord:
        person, thread, run_id = where
        values = {"id": uuid.uuid4(), **fields}
        return AgentMessageRecord(
            created_at=at, thread_id=uuid.UUID(thread), user_id=person, run_id=run_id, **values
        )

    @asynccontextmanager
    async def purge(self) -> AsyncIterator[CasePurge]:
        """The daily purge as the workers run it: its listing takes the sweep role."""
        shape = ProcessShape(role=ProcessRole.WORKERS)
        async with open_database_access(slot_urls(self.run_slot), shape) as workers:
            yield CasePurge(workers.transactions, self.clock)


@pytest_asyncio.fixture
async def feedback_bench(homes: DatabaseAccess, run_slot: RunSlot) -> AsyncIterator[FeedbackBench]:
    """The thread and rating routes over the slot's homes."""
    people, registry = People(), CollectorRegistry()
    ports = PortDirectory()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            MEMBERSHIP_READER.bind(MembershipDirectory()),
            CONSENT_READER.bind(people),
            ACCOUNT_PROFILE_READER.bind(people),
        ]
    )
    clock = TestClock()
    threads = Threads(
        homes.transactions, (ports, EffectLedger(EffectKeyMetrics(CollectorRegistry()))), clock
    )
    history = History(homes.transactions, threads, ActionCards(AgentToolCatalog(), ports))
    feedback = Feedback((homes.transactions, ports, threads), FeedbackMetrics(registry), clock)
    routers = (
        build_threads_router((threads, history), ports),
        build_feedback_router(feedback, ports),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield FeedbackBench(http, homes, run_slot, ports, clock, people, registry)
