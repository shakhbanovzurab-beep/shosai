"""The notes' stages over the slot's homes, the real AI port and a recorded model.

The port records each call's cost in the person's home, so a test reads the cost rows
back; the rewrite route runs over the slot's Valkey for its rate limit.
"""

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.records import OutboxMessage
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.features.identity.contracts import AUTHENTICATOR, CONSENT_READER
from shosai.features.notes.application.findings_stage import FindingsStage
from shosai.features.notes.application.notes_model import NotesModel
from shosai.features.notes.application.pipeline import PipelineEngine, StageHandler
from shosai.features.notes.application.run_rows import stage_state
from shosai.features.notes.application.stage_task import StagePayload, StageRetryError
from shosai.features.notes.application.write_up_rewrites import WriteUpRewrites
from shosai.features.notes.application.write_up_stage import WriteUpStage
from shosai.features.notes.channels.http.write_up import build_write_up_router
from shosai.features.notes.domain.runs import RunSource, Stage, initial_progress
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.notes_metrics import NotesMetrics
from shosai.features.notes.infrastructure.notes_records import FindingRecord, NotesRecord
from shosai.features.notes.infrastructure.pipeline_metrics import PipelineMetrics
from shosai.features.notes.infrastructure.run_records import RunRecord
from shosai.features.notes.module import NOTES
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import ACCESS_POLICY
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.core.ai.bench import Doubles, ai_bench, set_prices, set_rate
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.entitlement_bench import Clock
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.notes.recorded_model import RecordedModel
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

NOTES_MODEL = ModelRef(Provider.OPENROUTER, "probe/notes")
RECORDED = Path(__file__).parent / "recorded"
LARGE_BUDGET = 100_000
LIVE = RunSource.LIVE
type Json = dict[str, Any]


@dataclass
class Sent:
    """The stage tasks the engine queued."""

    payloads: list[StagePayload] = field(default_factory=list)

    async def send(self, task: TaskDeclaration[StagePayload], payload: StagePayload) -> str:
        del task
        self.payloads.append(payload)
        return str(len(self.payloads))


@dataclass(frozen=True, slots=True)
class Meeting:
    """A spoken, ended meeting with its live run."""

    scope: TenancyScope
    meeting_id: uuid.UUID
    run_id: uuid.UUID
    started_at: datetime
    first: StagePayload


@dataclass
class Consents:
    """Who consents to cross-border transfer."""

    people: set[uuid.UUID] = field(default_factory=set)

    async def cross_border(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        del session
        return user_id in self.people


def recorded(name: str) -> Json:
    """A recorded meeting: its lines and the model's answers as they came."""
    loaded: Json = json.loads((RECORDED / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


def spoken_lines(meeting: Json) -> list[tuple[int, int, str]]:
    """A recorded meeting's `(speaker, second, text)` lines."""
    return [(int(speaker), int(second), str(text)) for speaker, second, text in meeting["lines"]]


@dataclass
class NotesBench:
    """The stages, the engine, the rewrite route and what tests read back."""

    homes: DatabaseAccess
    run_slot: RunSlot
    model: RecordedModel
    ports: PortDirectory
    outbox: EventOutbox
    registry: CollectorRegistry
    notes_model: NotesModel
    sent: Sent
    clock: Clock
    http: httpx.AsyncClient
    consents: Consents
    engine: PipelineEngine

    def stages(self, budget: int = LARGE_BUDGET) -> dict[Stage, StageHandler]:
        """The two stages over a transcript budget."""
        transactions = self.homes.transactions
        return {
            Stage.FINDINGS: FindingsStage(transactions, (self.ports, self.notes_model), budget),
            Stage.WRITE_UP: WriteUpStage(
                transactions, (self.ports, self.outbox, self.notes_model), budget, self.clock
            ),
        }

    def with_budget(self, budget: int) -> None:
        """Run the stages over another budget."""
        self.engine = PipelineEngine(
            self.homes.transactions,
            (self.sent, PipelineMetrics(CollectorRegistry()), self.stages(budget)),
            self.clock,
        )

    async def meeting(self, lines: list[tuple[int, int, str]], home: Home = Home.EU) -> Meeting:
        """An ended meeting of `(speaker, second, text)` lines and its pending live run."""
        person, meeting_id, run_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        started, scope = self.clock() - timedelta(hours=1), TenancyScope(home, person)
        length = lines[-1][1] + 10 if lines else 60
        async with self.homes.transactions.begin(scope) as session:
            session.add(
                MeetingRecord(
                    id=meeting_id, user_id=person, title="Запуск приложения", status="completed",
                    started_at=started, ended_at=started + timedelta(seconds=length),
                    seconds=length, line_count=len(lines),
                )
            )  # fmt: skip
            await session.flush()
            session.add_all(
                TranscriptLineRecord(
                    session_id=meeting_id, seq=seq, meeting_started_at=started,
                    started_at=started + timedelta(seconds=second), start_ms=second * 1000,
                    duration_ms=4000, speaker_idx=speaker, text=text,
                )
                for seq, (speaker, second, text) in enumerate(lines, 1)
            )  # fmt: skip
            session.add(
                RunRecord(
                    id=run_id, session_id=meeting_id, user_id=person, source="live",
                    idempotency_key="live", stage_state=stage_state(initial_progress(LIVE)),
                    created_at=self.clock(), updated_at=self.clock(),
                )
            )  # fmt: skip
        first = StagePayload(home=home, user_id=person, run_id=run_id, stage=Stage.FINDINGS)
        return Meeting(scope, meeting_id, run_id, started, first)

    async def drive(self, payload: StagePayload) -> bool:
        """Deliver the stage and every stage it sends; False when a delivery asked a retry."""
        queue = [payload]
        while queue:
            current = queue.pop(0)
            before = len(self.sent.payloads)
            try:
                await self.engine.run_stage(current)
            except StageRetryError:
                return False
            queue.extend(self.sent.payloads[before:])
        return True

    async def findings(self, meeting: Meeting) -> list[FindingRecord]:
        """The meeting's findings by run and position."""
        async with self.homes.transactions.begin(meeting.scope, read_only=True) as session:
            rows = await session.scalars(
                select(FindingRecord)
                .where(FindingRecord.session_id == meeting.meeting_id)
                .order_by(FindingRecord.created_at, FindingRecord.position)
            )
            return list(rows.all())

    async def notes_or_run(
        self, meeting: Meeting
    ) -> tuple[NotesRecord | None, MeetingRecord, RunRecord]:
        """The meeting's notes if written, the meeting and its live run."""
        async with self.homes.transactions.begin(meeting.scope, read_only=True) as session:
            notes = await session.get(NotesRecord, meeting.meeting_id)
            record = await session.get(MeetingRecord, meeting.meeting_id)
            run = await session.get(RunRecord, meeting.run_id)
        assert record is not None
        assert run is not None
        return notes, record, run

    async def notes(self, meeting: Meeting) -> tuple[NotesRecord, MeetingRecord, RunRecord]:
        """The meeting's written notes, the meeting and its live run."""
        notes, record, run = await self.notes_or_run(meeting)
        assert notes is not None
        return notes, record, run

    async def ready_events(self, home: Home = Home.EU) -> list[Json]:
        """The `notes.meeting.notes_ready` payloads of a home, oldest first."""
        async with self.homes.transactions.begin(TenancyScope(home), read_only=True) as session:
            rows = await session.scalars(
                select(OutboxMessage)
                .where(OutboxMessage.event_type == "notes.meeting.notes_ready")
                .order_by(OutboxMessage.occurred_at)
            )
            return [dict(row.payload) for row in rows.all()]

    async def cost_keys(self, home: Home = Home.EU) -> list[str]:
        """The effect keys of the home's cost rows, in order."""
        rows = await fetch_rows(
            self.run_slot.claimed.connections[home],
            "SELECT effect_key FROM provider_costs ORDER BY effect_key",
        )
        return [str(row["effect_key"]) for row in rows]

    def answers(self, call: str, outcome: str) -> float:
        """How many answers of a call had the outcome."""
        sample = self.registry.get_sample_value(
            "shosai_notes_model_answers_total", {"call": call, "outcome": outcome}
        )
        return sample or 0.0


@pytest_asyncio.fixture
async def notes_bench(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> AsyncIterator[NotesBench]:
    """The notes' stages, priced, over a recorded model."""
    await set_prices(
        homes.transactions, NOTES_MODEL, input_token="0.000001", output_token="0.000004"
    )
    await set_rate(homes.transactions, "92.5000")
    model, registry, clock = RecordedModel(), CollectorRegistry(), Clock()
    ai = ai_bench(homes.transactions, doubles=Doubles(openrouter=model.client()))
    outbox = EventOutbox(EventTypes([*NOTES.events, *WORKSPACES.events]))
    ports, consents = PortDirectory(), Consents()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ACCESS_POLICY.bind(WorkspaceAccessPolicy(outbox, WorkspaceAuditLog())),
            CONSENT_READER.bind(consents),
        ]
    )
    notes_model = NotesModel(ai.providers, ModelRoute(NOTES_MODEL), NotesMetrics(registry))
    sent = Sent()
    bench_engine = PipelineEngine(homes.transactions, (sent, PipelineMetrics(registry), {}), clock)
    rewrites = WriteUpRewrites(
        homes.transactions, (ports, EffectLedger(EffectKeyMetrics(registry)), bench_engine), clock
    )
    limiter = RateLimiter(valkey, KeyValueMetrics(registry))
    router = build_write_up_router(rewrites, ports, limiter)
    async with client_of(build_probe_app(extra=(router,)).app) as http:
        bench = NotesBench(
            homes, run_slot, model, ports, outbox, registry, notes_model, sent, clock, http,
            consents, bench_engine,
        )  # fmt: skip
        bench.with_budget(LARGE_BUDGET)
        yield bench
