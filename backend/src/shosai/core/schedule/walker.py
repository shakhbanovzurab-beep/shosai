"""The scheduler's walk over the periodic jobs of one home (§12, F6-C13).

Every 5 s per home the walk claims the jobs that are due — `last_run_at` NULL or older than
the job's interval — in one conditional update that skips rows another walk holds, so two
scheduler processes never queue a job twice in one interval. It commits the claims, then
queues each job's tick outside any transaction (§14 rule 1). A tick that could not be queued
gives its claim back, so the next walk retries it; a tick skipped because the previous run
is still in flight keeps it, since that run is this interval's. A missed interval is due
once, whatever its length.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import structlog
from sqlalchemy import Interval, Text, column, func, or_, select, update, values
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.schedule.metrics import ScheduleMetrics
from shosai.core.schedule.records import ScheduleRun
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.core.tasks.payloads import HomeTaskPayload, TaskPayload

log = structlog.stdlib.get_logger(__name__)


class TickSender(Protocol):
    """What the walk needs from the task sender: queue a tick unless one is in flight."""

    async def send_tick[P: TaskPayload](
        self, task: TaskDeclaration[P], payload: P, *marker: str
    ) -> bool:
        """Queue the tick; False when the previous one with this marker is in flight."""
        ...


@dataclass(frozen=True, slots=True)
class Claim:
    """A job run this walk holds: the job, its previous run and the time of this one."""

    job: str
    previous: datetime | None
    claimed_at: datetime


@dataclass(slots=True)
class WalkResult:
    """What one walk over a home did."""

    queued: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def check_job_names(jobs: Sequence[PeriodicJob]) -> None:
    """Refuse a job declared twice: its runs would share one row."""
    names = [job.name for job in jobs]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        message = f"периодические задачи объявлены дважды: {', '.join(duplicates)}"
        raise ValueError(message)


class ScheduleWalker:
    """Claims and queues the due periodic jobs of a home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        sender: TickSender,
        metrics: ScheduleMetrics,
        jobs: Sequence[PeriodicJob],
    ) -> None:
        check_job_names(jobs)
        self._transactions = transactions
        self._sender = sender
        self._metrics = metrics
        self._jobs = {job.name: job for job in jobs}
        self._known: set[Home] = set()

    async def walk(self, home: Home) -> WalkResult:
        """Queue every due job of the home once; give back the claims that failed."""
        jobs = [job for job in self._jobs.values() if home in job.homes]
        result = WalkResult()
        if not jobs:
            return result
        await self._register(home, jobs)
        claims = await self._claim(home, jobs)
        failed: list[Claim] = []
        for claim in claims:
            job = self._jobs[claim.job]
            try:
                queued = await self._sender.send_tick(
                    job.task, HomeTaskPayload(home=home), home.value
                )
            except TaskQueueUnavailableError:
                failed.append(claim)
                self._metrics.count(claim.job, home, "failed")
                continue
            (result.queued if queued else result.skipped).append(claim.job)
            self._metrics.count(claim.job, home, "queued" if queued else "skipped")
        if failed:
            await self._give_back(home, failed)
            result.failed = [claim.job for claim in failed]
            log.warning(
                "Периодические задачи не поставлены: захват возвращён",
                home=home.value,
                jobs=result.failed,
            )
        return result

    async def _register(self, home: Home, jobs: Sequence[PeriodicJob]) -> None:
        # Строка задачи создаётся один раз за жизнь процесса; существующую не трогаем.
        if home in self._known:
            return
        statement = (
            insert(ScheduleRun)
            .values([{"job_name": job.name} for job in jobs])
            .on_conflict_do_nothing()
        )
        async with self._transactions.begin(TenancyScope(home)) as session:
            await session.execute(statement)
        self._known.add(home)

    async def _claim(self, home: Home, jobs: Sequence[PeriodicJob]) -> list[Claim]:
        due_jobs = values(column("job_name", Text), column("every", Interval), name="due").data(
            [(job.name, job.every) for job in jobs]
        )
        held = (
            select(ScheduleRun.job_name, ScheduleRun.last_run_at.label("previous"))
            .join(due_jobs, due_jobs.c.job_name == ScheduleRun.job_name)
            .where(
                or_(
                    ScheduleRun.last_run_at.is_(None),
                    ScheduleRun.last_run_at <= func.now() - due_jobs.c.every,
                )
            )
            .with_for_update(of=ScheduleRun, skip_locked=True)
            .subquery("held")
        )
        statement = (
            update(ScheduleRun)
            .where(ScheduleRun.job_name == held.c.job_name)
            .values(last_run_at=func.now())
            .returning(ScheduleRun.job_name, held.c.previous, ScheduleRun.last_run_at)
        )
        async with self._transactions.begin(TenancyScope(home)) as session:
            rows = (await session.execute(statement)).all()
        return sorted(
            (
                Claim(job=job, previous=previous, claimed_at=claimed)
                for job, previous, claimed in rows
            ),
            key=lambda claim: claim.job,
        )

    async def _give_back(self, home: Home, claims: Sequence[Claim]) -> None:
        async with self._transactions.begin(TenancyScope(home)) as session:
            for claim in claims:
                # Только свой захват: другой обход мог уже поставить задачу заново.
                await session.execute(
                    update(ScheduleRun)
                    .where(
                        ScheduleRun.job_name == claim.job,
                        ScheduleRun.last_run_at == claim.claimed_at,
                    )
                    .values(last_run_at=claim.previous)
                )
