"""Memory's tasks: a turn's admission after `agent.turn.completed` (step 5), the embedding pass
of each home, once a minute (step 4), a person's summary rewritten in the background (step 7),
a meeting's recollection after its first notes (step 9), and per home the day's upkeep on a
cursor every ten minutes, the hourly settling of erasure marks and the hourly check of the
switch's invariant (step 8).

A fact written without a vector is recalled from the next minute on; a pass lost or repeated
changes nothing the next one would not, since a vector lands only on a fact still waiting for
one.
"""

from datetime import datetime, timedelta
from typing import Final, Protocol
from uuid import UUID

from shosai.core.ai.errors import AiCallError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import (
    MAX_DELIVERIES,
    NO_RETRY,
    TRANSIENT_FAILURES,
    RetryPolicy,
    TaskDeclaration,
    TaskHandler,
    TaskKind,
)
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.memory.application.departures import Departures
from shosai.features.memory.application.embedding_pass import EmbeddingPass
from shosai.features.memory.application.invariants import MemoryInvariants
from shosai.features.memory.application.meeting_recollection import MeetingRecollection
from shosai.features.memory.application.summaries import Summaries, SummaryQueue
from shosai.features.memory.application.turn_admission import TurnAdmission
from shosai.features.memory.application.upkeep import Upkeep
from shosai.features.memory.infrastructure.metrics import SummaryTrigger


class TurnTask(HomeTaskPayload):
    """One finished turn of a person, and when it ended (none in tasks queued before step 11)."""

    run_id: UUID
    ended_at: datetime | None = None


# Сбой поставщика модели — тоже повод повторить: запись приёма идемпотентна по прогону.
ADMIT_TURN: Final = TaskDeclaration(
    name="memory.admit_turn",
    queue=TaskQueue.DEFAULT,
    payload=TurnTask,
    deadline=timedelta(minutes=3),
    retry=RetryPolicy(MAX_DELIVERIES, (*TRANSIENT_FAILURES, AiCallError)),
)


class SummaryTask(HomeTaskPayload):
    """A person's summary to rewrite, and why."""

    trigger: SummaryTrigger


class MeetingTask(HomeTaskPayload):
    """One meeting of its owner, with its first notes."""

    meeting_id: UUID


# Сбой поставщика модели — повод повторить: запись воспоминаний идемпотентна по встрече.
RECOLLECT: Final = TaskDeclaration(
    name="memory.recollect_meeting",
    queue=TaskQueue.DEFAULT,
    payload=MeetingTask,
    deadline=timedelta(minutes=3),
    retry=RetryPolicy(MAX_DELIVERIES, (*TRANSIENT_FAILURES, AiCallError)),
)
# Сводка, не написанная из-за модели, ждёт следующего открытия: повторяется только сбой связи.
WRITE_SUMMARY: Final = TaskDeclaration(
    name="memory.write_summary",
    queue=TaskQueue.DEFAULT,
    payload=SummaryTask,
    deadline=timedelta(minutes=3),
    retry=RetryPolicy(MAX_DELIVERIES, TRANSIENT_FAILURES),
)
EMBED_WAITING: Final = TaskDeclaration(
    name="memory.embed_waiting",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=2),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
UPKEEP: Final = TaskDeclaration(
    name="memory.upkeep",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=8),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
SETTLE_MARKS: Final = TaskDeclaration(
    name="memory.settle_marks",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
CHECK_INVARIANT: Final = TaskDeclaration(
    name="memory.check_invariant",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=2),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PERIODIC_JOBS: Final = (
    PeriodicJob(EMBED_WAITING, every=timedelta(minutes=1)),
    PeriodicJob(UPKEEP, every=timedelta(minutes=10)),
    PeriodicJob(SETTLE_MARKS, every=timedelta(hours=1)),
    PeriodicJob(CHECK_INVARIANT, every=timedelta(hours=1)),
)


def embedding_tick(embedding: EmbeddingPass) -> TaskHandler[HomeTaskPayload]:
    """The pass of the payload's home."""

    async def embed(payload: HomeTaskPayload) -> None:
        await embedding.run(payload.home)

    return TaskHandler(EMBED_WAITING, embed)


def turn_admission(admission: TurnAdmission) -> TaskHandler[TurnTask]:
    """The admission of the payload's turn."""

    async def admit(payload: TurnTask) -> None:
        if payload.user_id is not None:
            await admission.admit(payload.home, payload.user_id, payload.run_id, payload.ended_at)

    return TaskHandler(ADMIT_TURN, admit)


class SummarySender(Protocol):
    """Sends a summary's rewrite to its queue."""

    async def send(self, task: TaskDeclaration[SummaryTask], payload: SummaryTask) -> str:
        """Queue the task; its id."""
        ...


def summary_queue(sender: SummarySender) -> SummaryQueue:
    """How the summaries queue a rewrite."""

    async def queue(scope: TenancyScope, trigger: SummaryTrigger) -> None:
        payload = SummaryTask(home=scope.home, user_id=scope.user_id, trigger=trigger)
        await sender.send(WRITE_SUMMARY, payload)

    return queue


def summary_writes(summaries: Summaries) -> TaskHandler[SummaryTask]:
    """The rewrite of the payload's summary."""

    async def write(payload: SummaryTask) -> None:
        if payload.user_id is not None:
            await summaries.write(payload.scope(), payload.trigger)

    return TaskHandler(WRITE_SUMMARY, write)


def meeting_recollection(recollection: MeetingRecollection) -> TaskHandler[MeetingTask]:
    """The recollection of the payload's meeting."""

    async def recollect(payload: MeetingTask) -> None:
        if payload.user_id is not None:
            await recollection.recollect(payload.home, payload.user_id, payload.meeting_id)

    return TaskHandler(RECOLLECT, recollect)


def upkeep_ticks(
    upkeep: Upkeep, departures: Departures, invariants: MemoryInvariants
) -> tuple[TaskHandler[HomeTaskPayload], ...]:
    """The upkeep's day, the settling of marks and the invariant's check of a home."""

    async def tend(payload: HomeTaskPayload) -> None:
        await upkeep.run(payload.home)

    async def settle(payload: HomeTaskPayload) -> None:
        await departures.settle(payload.home)

    async def check(payload: HomeTaskPayload) -> None:
        await invariants.check(payload.home)

    return (
        TaskHandler(UPKEEP, tend),
        TaskHandler(SETTLE_MARKS, settle),
        TaskHandler(CHECK_INVARIANT, check),
    )
