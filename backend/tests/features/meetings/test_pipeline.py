"""The pipeline's engine under faults: redeliveries, killed workers, retries (meetings step 5)."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import cast

import pytest
from prometheus_client import CollectorRegistry

from shosai.core.config.roles import ProcessRole
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.features.meetings.application.pipeline import (
    PipelineEngine,
    StageFailedError,
    StageHandler,
    StageWork,
)
from shosai.features.meetings.application.run_recovery import RunRecovery
from shosai.features.meetings.application.run_rows import progress_of, stage_state
from shosai.features.meetings.application.stage_task import RUN_STAGE, StagePayload, StageRetryError
from shosai.features.meetings.domain.runs import (
    RunSource,
    RunState,
    Stage,
    StageStatus,
    initial_progress,
)
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.pipeline_metrics import PipelineMetrics
from shosai.features.meetings.infrastructure.run_records import RunRecord
from tests.features.billing.entitlement_bench import Clock
from tests.features.files.upload_bench import Guard, GuardedTransactions
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot


@dataclass
class Sent:
    """The stage tasks the engine queued."""

    payloads: list[StagePayload] = field(default_factory=list)

    async def send(self, task: TaskDeclaration[StagePayload], payload: StagePayload) -> str:
        assert task is RUN_STAGE
        self.payloads.append(payload)
        return str(len(self.payloads))


@dataclass
class Scripted:
    """A stage that fails with the codes given, then succeeds; it checks no transaction is open."""

    guard: Guard
    failures: list[str | None] = field(default_factory=list)
    calls: list[int] = field(default_factory=list)

    async def run(self, work: StageWork) -> None:
        self.guard.check()
        self.calls.append(work.attempt)
        code = self.failures.pop(0) if self.failures else None
        if code == "killed":
            raise asyncio.CancelledError
        if code is not None:
            raise StageFailedError(code)


@dataclass
class Pipeline:
    """An engine over guarded transactions, its handlers, what it sent and its clock."""

    homes: DatabaseAccess
    engine: PipelineEngine
    handlers: dict[Stage, Scripted]
    sent: Sent
    clock: Clock
    run_slot: RunSlot
    metrics: PipelineMetrics
    registry: CollectorRegistry

    async def run(self, source: RunSource) -> StagePayload:
        """A meeting with a new run of the source; its first stage's payload."""
        person, meeting, run = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with self.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
            session.add(
                MeetingRecord(id=meeting, user_id=person, title="Встреча", started_at=self.clock())
            )
            await session.flush()
            session.add(
                RunRecord(
                    id=run, session_id=meeting, user_id=person, source=source.value,
                    idempotency_key=f"test:{run}",
                    stage_state=stage_state(initial_progress(source)),
                    created_at=self.clock(), updated_at=self.clock(),
                )
            )  # fmt: skip
        stage = next(iter(initial_progress(source)))
        return StagePayload(home=Home.RU, user_id=person, run_id=run, stage=stage)

    async def state(self, payload: StagePayload) -> tuple[RunState, dict[Stage, StageStatus]]:
        """The run's state and its stages' statuses."""
        async with self.homes.transactions.begin(payload.scope(), read_only=True) as session:
            run = await session.get(RunRecord, payload.run_id)
        assert run is not None
        return RunState(run.state), {s: r.status for s, r in progress_of(run.stage_state).items()}

    @asynccontextmanager
    async def recovery(self) -> AsyncIterator[RunRecovery]:
        """The recovery sweep as the workers run it."""
        shape = ProcessShape(role=ProcessRole.WORKERS)
        async with open_database_access(slot_urls(self.run_slot), shape) as workers:
            yield RunRecovery(workers.transactions, (self.engine, self.metrics), self.clock)


@pytest.fixture
def pipeline(homes: DatabaseAccess, run_slot: RunSlot) -> Pipeline:
    guard, sent, clock, registry = Guard(), Sent(), Clock(), CollectorRegistry()
    handlers = {stage: Scripted(guard) for stage in Stage}
    metrics = PipelineMetrics(registry)
    known: dict[Stage, StageHandler] = dict(handlers)
    transactions = cast("HomeTransactions", GuardedTransactions(homes.transactions, guard))
    engine = PipelineEngine(transactions, (sent, metrics, known), clock)
    return Pipeline(homes, engine, handlers, sent, clock, run_slot, metrics, registry)


async def test_a_run_goes_through_its_stages_once_even_when_a_stage_is_delivered_again(
    pipeline: Pipeline,
) -> None:
    first = await pipeline.run(RunSource.LIVE)

    await pipeline.engine.run_stage(first)
    await pipeline.engine.run_stage(first)
    [second] = pipeline.sent.payloads
    await pipeline.engine.run_stage(second)
    await pipeline.engine.run_stage(second)

    assert second.stage is Stage.WRITE_UP
    assert pipeline.handlers[Stage.FINDINGS].calls == [1]
    assert pipeline.handlers[Stage.WRITE_UP].calls == [1]
    assert await pipeline.state(first) == (
        RunState.SUCCEEDED,
        {Stage.FINDINGS: StageStatus.DONE, Stage.WRITE_UP: StageStatus.DONE},
    )
    assert (
        pipeline.registry.get_sample_value(
            "shosai_meetings_runs_total", {"source": "live", "outcome": "succeeded"}
        )
        == 1
    )


async def test_a_stage_that_keeps_failing_stops_after_three_attempts_on_any_path(
    pipeline: Pipeline,
) -> None:
    payload = await pipeline.run(RunSource.LIVE)
    findings = pipeline.handlers[Stage.FINDINGS]
    findings.failures = ["provider_error", "killed", "provider_error", "provider_error"]

    with pytest.raises(StageRetryError):
        await pipeline.engine.run_stage(payload)
    with pytest.raises(asyncio.CancelledError):
        await pipeline.engine.run_stage(payload)
    await pipeline.engine.run_stage(payload)
    pipeline.clock.advance(RUN_STAGE.hold_limit + timedelta(minutes=1))
    async with pipeline.recovery() as recovery:
        resent = await recovery.run(Home.RU)
    await pipeline.engine.run_stage(pipeline.sent.payloads[-1])
    await pipeline.engine.run_stage(payload)

    assert resent == 1
    assert findings.calls == [1, 2, 3]
    assert await pipeline.state(payload) == (
        RunState.FAILED,
        {Stage.FINDINGS: StageStatus.FAILED, Stage.WRITE_UP: StageStatus.PENDING},
    )


async def test_a_killed_worker_s_stage_is_taken_over_from_the_database(
    pipeline: Pipeline,
) -> None:
    payload = await pipeline.run(RunSource.LIVE)
    pipeline.handlers[Stage.FINDINGS].failures = ["killed"]

    with pytest.raises(asyncio.CancelledError):
        await pipeline.engine.run_stage(payload)
    async with pipeline.recovery() as recovery:
        early = await recovery.run(Home.RU)
        pipeline.clock.advance(RUN_STAGE.hold_limit + timedelta(seconds=1))
        late = await recovery.run(Home.RU)
    await pipeline.engine.run_stage(pipeline.sent.payloads[-1])

    assert (early, late) == (0, 1)
    assert pipeline.handlers[Stage.FINDINGS].calls == [1, 2]
    assert (await pipeline.state(payload))[1][Stage.FINDINGS] is StageStatus.DONE


async def test_a_code_retrying_cannot_cure_fails_at_once_and_a_non_critical_one_lets_the_run_go_on(
    pipeline: Pipeline,
) -> None:
    refused = await pipeline.run(RunSource.LIVE)
    pipeline.handlers[Stage.FINDINGS].failures = ["consent_required"]
    await pipeline.engine.run_stage(refused)
    imported = await pipeline.run(RunSource.IMPORT)
    pipeline.handlers[Stage.DIARIZE].failures = ["provider_error"] * 3

    payload = imported
    for _ in range(12):
        try:
            await pipeline.engine.run_stage(payload)
        except StageRetryError:
            continue
        if pipeline.sent.payloads and pipeline.sent.payloads[-1].run_id == imported.run_id:
            payload = pipeline.sent.payloads[-1]

    assert (await pipeline.state(refused))[0] is RunState.FAILED
    state, stages = await pipeline.state(imported)
    assert state is RunState.PARTIALLY_COMPLETED
    assert stages[Stage.DIARIZE] is StageStatus.FAILED
    assert stages[Stage.WRITE_UP] is StageStatus.DONE


async def test_a_stage_without_a_handler_waits_and_nothing_is_sent(
    homes: DatabaseAccess, pipeline: Pipeline
) -> None:
    payload = await pipeline.run(RunSource.LIVE)
    engine = PipelineEngine(
        homes.transactions, (pipeline.sent, pipeline.metrics, {}), pipeline.clock
    )

    await engine.run_stage(payload)

    assert pipeline.sent.payloads == []
    assert (await pipeline.state(payload))[0] is RunState.PENDING
