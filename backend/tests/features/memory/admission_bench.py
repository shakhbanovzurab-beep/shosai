"""A turn's admission over the slot's homes: the turn's words, the extraction model and the
embeddings as doubles (memory step 5)."""

import json
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import Taint
from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.requests import ChatRequest
from shosai.core.ai.results import ChatResult, Usage
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.contracts.memory import PERSON_WORDS, TurnWords
from shosai.features.identity.contracts import CONSENT_READER
from shosai.features.memory.application.turn_admission import TurnAdmission
from shosai.features.memory.infrastructure.embeddings import Embedder
from shosai.features.memory.infrastructure.extractor import Extractor
from shosai.features.memory.infrastructure.metrics import MemoryMetrics
from shosai.features.memory.infrastructure.records import MemoryFactRecord
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from tests.features.memory.facts_api_bench import Spaces
from tests.features.memory.recall_bench import ROUTE, Consents, VectorModel
from tests.harness.database_access import DatabaseAccess

CHAT = ModelRoute(ModelRef(Provider.OPENROUTER, "google/gemini-3.8-flash"))


@dataclass
class Statements:
    """The extraction model: the statements it finds, as its JSON answer."""

    found: list[dict[str, object]] = field(default_factory=list)
    calls: list[ChatRequest] = field(default_factory=list)

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """The JSON object of the statements."""
        del context
        self.calls.append(request)
        text = json.dumps({"statements": self.found})
        return ChatResult(text, (), "stop", route.primary, Usage(input_tokens=1, output_tokens=1))


@dataclass
class Turns:
    """The person's words of each run, as the agent would give them."""

    words: dict[uuid.UUID, TurnWords] = field(default_factory=dict)

    async def of_turn(
        self, session: AsyncSession, user_id: uuid.UUID, run_id: uuid.UUID
    ) -> TurnWords | None:
        """The run's words, or None for a run the agent would not give."""
        del session, user_id
        return self.words.get(run_id)

    def said(
        self, text: str, *, taint: Taint = Taint.NONE, org_id: uuid.UUID | None = None
    ) -> uuid.UUID:
        """A finished turn with the person's words: its run."""
        run_id = uuid.uuid4()
        self.words[run_id] = TurnWords(
            thread_id=uuid.uuid4(), message_id=uuid.uuid4(), org_id=org_id, text=text,
            taint=taint, said_at=datetime.now(UTC), before=(),
        )  # fmt: skip
        return run_id


@dataclass(frozen=True, slots=True)
class AdmissionBench:
    """The admission and its doubles."""

    homes: DatabaseAccess
    admission: TurnAdmission
    statements: Statements
    turns: Turns
    vectors: VectorModel
    consents: Consents

    async def facts(self, person: uuid.UUID) -> Sequence[MemoryFactRecord]:
        """Every fact of the person, ended ones too, oldest first."""
        scope = TenancyScope(Home.RU, person)
        async with self.homes.transactions.begin(scope, read_only=True) as session:
            return list(
                await session.scalars(
                    select(MemoryFactRecord).order_by(MemoryFactRecord.created_at)
                )
            )


@pytest_asyncio.fixture
async def admission_bench(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[AdmissionBench]:
    statements, turns, vectors, consents = Statements(), Turns(), VectorModel(), Consents()
    ports = PortDirectory()
    ports.install(
        [
            PERSON_WORDS.bind(turns),
            CONSENT_READER.bind(consents),
            MEMBERSHIP_READER.bind(Spaces()),
        ]
    )
    registry = CollectorRegistry()
    admission = TurnAdmission(
        homes.transactions,
        (Extractor(statements, CHAT), Embedder(vectors, ROUTE)),
        (ports, EffectLedger(EffectKeyMetrics(registry)), valkey, MemoryMetrics(registry)),
    )
    yield AdmissionBench(homes, admission, statements, turns, vectors, consents)
