"""Memory's daily upkeep of one home, person by person (memory step 8, plan §3.6).

Each person who holds any fact is tended once a day, in their own transaction under their
admission lock: current facts faded below the expiry level end as `expired` (pinned ones never
fade). Candidates unanswered for 30 days end the same way, the draft's carried-over ones
excepted. Facts ended or replaced more than 180 days ago are purged, and a stale summary of a
person whose memory is on is queued for a rewrite. The day's cursor in Valkey says who was
served last, so the ticks of a day share the work and a repeated tick changes nothing: a
person tended again finds nothing left to do. Vectors of an older model are the embedding
pass's work.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.memory.application.admission_writer import ADMISSION_LOCK_SPACE, person_key
from shosai.features.memory.application.fact_rows import FACT, fact_of
from shosai.features.memory.application.summaries import Summaries
from shosai.features.memory.application.switch import memory_on
from shosai.features.memory.domain.decay import faded
from shosai.features.memory.domain.facts import EndReason, FactStatus, MemorySource
from shosai.features.memory.domain.lifetimes import CANDIDATE_LIFETIME, ENDED_KEPT
from shosai.features.memory.infrastructure.metrics import MemoryMetrics, SummaryTrigger, UpkeepPart

BATCH: Final = 200
# Тик укладывается в своё время: остальных людей дня берут следующие тики.
TICK_BUDGET: Final = timedelta(minutes=4)
CURSOR_PREFIX: Final = "memory:upkeep:"
DONE: Final = "done"
CURSOR_TTL: Final = timedelta(days=2)


@dataclass(frozen=True, slots=True)
class Tended:
    """What one person's upkeep changed."""

    expired: int
    purged: int


def cursor_key(home: Home, day: str) -> str:
    """The day's cursor of a home."""
    return f"{CURSOR_PREFIX}{home.value}:{day}"


class Upkeep:
    """Tends each person's memory once a day."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[Summaries, Redis, MemoryMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transactions = transactions
        self._summaries, self._valkey, self._metrics = collaborators
        self._clock = clock
        self._monotonic = monotonic

    async def run(self, home: Home) -> int:
        """Tend the day's next people within the tick's time; how many were tended."""
        key = cursor_key(home, self._clock().date().isoformat())
        stored = await self._valkey.get(key)
        cursor = stored.decode() if isinstance(stored, bytes) else stored
        if cursor == DONE:
            return 0
        started, tended = self._monotonic(), 0
        after = UUID(cursor) if cursor else None
        keep = int(CURSOR_TTL.total_seconds())
        while self._monotonic() - started < TICK_BUDGET.total_seconds():
            people = await self._next(home, after)
            for user_id in people:
                await self.tend(TenancyScope(home, user_id))
                await self._valkey.set(key, str(user_id), ex=keep)
            tended += len(people)
            if len(people) < BATCH:
                await self._valkey.set(key, DONE, ex=keep)
                break
            after = people[-1]
        return tended

    async def tend(self, scope: TenancyScope) -> Tended:
        """One person's upkeep."""
        user_id = scope.user_id
        if user_id is None:
            message = "уход за памятью — от имени человека"
            raise ValueError(message)
        now = self._clock()
        async with self._transactions.begin(scope) as session:
            await session.execute(
                select(func.pg_advisory_xact_lock(ADMISSION_LOCK_SPACE, person_key(user_id)))
            )
            expired = await self._expire(session, user_id, now)
            purged = await self._purge(session, user_id, now)
            on = await memory_on(session, user_id)
        self._metrics.upkept(UpkeepPart.EXPIRED, expired)
        self._metrics.upkept(UpkeepPart.PURGED, purged)
        if on and (await self._summaries.view(scope, rewrite=False)).stale:
            await self._summaries.queue(scope, SummaryTrigger.UPKEEP)
        return Tended(expired, purged)

    @staticmethod
    async def _expire(session: AsyncSession, user_id: UUID, now: datetime) -> int:
        """End the faded facts and the candidates left unanswered."""
        current = await session.scalars(
            select(FACT)
            .where(FACT.user_id == user_id, FACT.status == FactStatus.ACTIVE.value)
            .where(FACT.valid_to.is_(None), FACT.pinned.is_(False))
        )
        gone = [row.id for row in current if faded(fact_of(row), now)]
        unanswered = (
            (FACT.status == FactStatus.CANDIDATE.value)
            & FACT.valid_to.is_(None)
            & (FACT.source_kind != MemorySource.IMPORTED.value)
            & (FACT.created_at < now - CANDIDATE_LIFETIME)
        )
        ended = await session.scalars(
            update(FACT)
            .where(FACT.user_id == user_id, or_(FACT.id.in_(gone), unanswered))
            .values(status=FactStatus.FORGOTTEN.value, pinned=False,
                    ended_reason=EndReason.EXPIRED.value, ended_at=now, updated_at=now)
            .returning(FACT.id)
        )  # fmt: skip
        return len(list(ended))

    @staticmethod
    async def _purge(session: AsyncSession, user_id: UUID, now: datetime) -> int:
        """Delete the facts ended or replaced more than 180 days ago."""
        horizon = now - ENDED_KEPT
        old = or_(
            (FACT.status == FactStatus.FORGOTTEN.value) & (FACT.ended_at < horizon),
            FACT.valid_to < horizon,
        )
        purged = await session.scalars(
            delete(FACT).where(FACT.user_id == user_id, old).returning(FACT.id)
        )
        return len(list(purged))

    async def _next(self, home: Home, after: UUID | None) -> list[UUID]:
        """The next people of the home who hold any fact, through the sweep role."""
        query = select(FACT.user_id).distinct().order_by(FACT.user_id).limit(BATCH)
        if after is not None:
            query = query.where(FACT.user_id > after)
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            return list(await session.scalars(query))
