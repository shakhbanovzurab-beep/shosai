"""A meeting's recollection over the slot's homes: the meeting, its findings, the owner's profile,
the model and the embeddings as doubles (memory step 9)."""

import uuid
from collections.abc import AsyncIterator, Collection, Mapping, Sequence
from dataclasses import dataclass, field

import pytest_asyncio
from prometheus_client import CollectorRegistry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, CONSENT_READER
from shosai.features.memory.application.meeting_recollection import MeetingRecollection
from shosai.features.memory.infrastructure.embeddings import Embedder
from shosai.features.memory.infrastructure.metrics import MemoryMetrics
from shosai.features.memory.infrastructure.recollector import Recollector
from shosai.features.memory.infrastructure.records import MemoryFactRecord
from shosai.features.notes.contracts import (
    MEETING_FINDINGS,
    MEETING_READER,
    FindingFacts,
    FindingKind,
    MeetingFacts,
    MeetingNotFoundError,
    MeetingStatus,
    ParticipantFacts,
    TranscriptPage,
)
from shosai.features.workspaces.contracts import Viewer
from tests.features.memory.admission_bench import CHAT
from tests.features.memory.facts_api_bench import START
from tests.features.memory.recall_bench import ROUTE, Consents, VectorModel
from tests.features.memory.summary_bench import Languages, Writer
from tests.harness.database_access import DatabaseAccess

SUMMARY = "Anna Petrova and Mara reviewed the launch. Mara leads design."


@dataclass
class Notes:
    """Meetings by id with their owner, space and findings, read by their owner only."""

    meetings: dict[uuid.UUID, MeetingFacts] = field(default_factory=dict)
    findings: dict[uuid.UUID, list[FindingFacts]] = field(default_factory=dict)

    def held(
        self, owner: uuid.UUID, points: Sequence[str], org_id: uuid.UUID | None = None
    ) -> tuple[uuid.UUID, list[uuid.UUID]]:
        """A completed meeting of the owner with its key points: its id and the points' ids."""
        meeting_id = uuid.uuid4()
        self.meetings[meeting_id] = MeetingFacts(
            meeting_id=meeting_id, user_id=owner, org_id=org_id, title="Launch review",
            status=MeetingStatus.COMPLETED, started_at=START, ended_at=START, seconds=1800,
            participants=(ParticipantFacts("Anna Petrova", "anna@example.com"),
                          ParticipantFacts("Mara", None)),
            summary=SUMMARY,
        )  # fmt: skip
        ids = [uuid.uuid4() for _ in points]
        self.findings[meeting_id] = [
            FindingFacts(finding_id, FindingKind.KEY_POINT, text, None, None, None, 0, 1000, "")
            for finding_id, text in zip(ids, points, strict=True)
        ]
        return meeting_id, ids

    async def facts(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, MeetingFacts]:
        """The owner's meetings among the ids."""
        del session
        return {
            meeting_id: meeting
            for meeting_id, meeting in self.meetings.items()
            if meeting_id in meeting_ids and meeting.user_id == viewer.user_id
        }

    async def transcript(
        self, home: Home, viewer: Viewer, meeting_id: uuid.UUID, cursor: str | None, limit: int
    ) -> TranscriptPage:
        """A recollection never reads the transcript."""
        del home, viewer, meeting_id, cursor, limit
        raise MeetingNotFoundError

    async def readable(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[uuid.UUID]
    ) -> frozenset[uuid.UUID]:
        """The owner's meetings among the ids."""
        return frozenset(await self.facts(session, viewer, meeting_ids))

    async def of(
        self, session: AsyncSession, viewer: Viewer, meeting_id: uuid.UUID
    ) -> Sequence[FindingFacts]:
        """The meeting's findings, for its owner."""
        if meeting_id not in await self.facts(session, viewer, [meeting_id]):
            raise MeetingNotFoundError
        return self.findings[meeting_id]


@dataclass(frozen=True, slots=True)
class RecollectionBench:
    """The recollection and its doubles."""

    homes: DatabaseAccess
    notes: Notes
    writer: Writer
    consents: Consents
    vectors: VectorModel
    recollection: MeetingRecollection

    async def facts(self, person: uuid.UUID) -> list[MemoryFactRecord]:
        """The person's facts, oldest first."""
        scope = TenancyScope(Home.RU, person)
        async with self.homes.transactions.begin(scope, read_only=True) as session:
            found = await session.scalars(
                select(MemoryFactRecord)
                .where(MemoryFactRecord.user_id == person)
                .order_by(MemoryFactRecord.created_at, MemoryFactRecord.statement)
            )
            return list(found)


@pytest_asyncio.fixture
async def recollection_bench(homes: DatabaseAccess) -> AsyncIterator[RecollectionBench]:
    notes, writer, consents, vectors = Notes(), Writer(), Consents(), VectorModel()
    ports = PortDirectory()
    ports.install(
        [
            CONSENT_READER.bind(consents),
            MEETING_READER.bind(notes),
            MEETING_FINDINGS.bind(notes),
            ACCOUNT_PROFILE_READER.bind(Languages()),
        ]
    )
    registry = CollectorRegistry()
    recollection = MeetingRecollection(
        homes.transactions,
        (Recollector(writer, CHAT), Embedder(vectors, ROUTE)),
        (ports, EffectLedger(EffectKeyMetrics(registry)), MemoryMetrics(registry)),
    )
    yield RecollectionBench(homes, notes, writer, consents, vectors, recollection)
