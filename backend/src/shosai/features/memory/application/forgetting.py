"""Forgetting for good (the owner's decision of 2026-10-27, ADR 0071 MM-D9).

A forgotten, turned-down or replaced fact stays a day, while the person can take it back; then
the hourly pass deletes it, person by person in their own transaction under their admission
lock. What the person forgot or turned down leaves a trace — the vector, its model and the
moment, never the text — and admission skips a statement close to a trace for 90 days unless
the person asks for it; the daily upkeep drops older traces. "Forget everything" deletes the
person's facts, traces and summary at once and leaves nothing.
"""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import ColumnElement, and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.memory.application.admission_writer import ADMISSION_LOCK_SPACE, person_key
from shosai.features.memory.application.fact_rows import FACT
from shosai.features.memory.domain.facts import RESTORE_WINDOW, FactStatus
from shosai.features.memory.domain.lifetimes import REFUSAL_KEPT, REFUSALS
from shosai.features.memory.infrastructure.metrics import MemoryMetrics, UpkeepPart
from shosai.features.memory.infrastructure.records import MemoryRefusalRecord, MemorySummaryRecord

TRACE = MemoryRefusalRecord
BATCH: Final = 200
REASONS: Final = tuple(reason.value for reason in REFUSALS)
TRACE_COLUMNS: Final = ("id", "user_id", "embedding", "embedding_model", "refused_at")


def ended_before(cut: datetime) -> ColumnElement[bool]:
    """Facts forgotten, turned down, expired or replaced before the moment."""
    forgotten = and_(FACT.status == FactStatus.FORGOTTEN.value, FACT.ended_at < cut)
    return or_(forgotten, FACT.valid_to < cut)


async def let_go(session: AsyncSession, user_id: UUID, now: datetime) -> int:
    """Delete the person's ended facts past their day, keeping a trace of each refusal."""
    cut = now - RESTORE_WINDOW
    refusals = select(
        FACT.id, FACT.user_id, FACT.embedding, FACT.embedding_model, FACT.ended_at
    ).where(
        FACT.user_id == user_id,
        FACT.status == FactStatus.FORGOTTEN.value,
        FACT.ended_reason.in_(REASONS),
        FACT.ended_at < cut,
        FACT.ended_at >= now - REFUSAL_KEPT,
        FACT.embedding.is_not(None),
        FACT.embedding_model.is_not(None),
    )
    await session.execute(
        insert(TRACE).from_select(TRACE_COLUMNS, refusals).on_conflict_do_nothing()
    )
    gone = await session.scalars(
        delete(FACT).where(FACT.user_id == user_id, ended_before(cut)).returning(FACT.id)
    )
    return len(list(gone))


async def drop_old_traces(session: AsyncSession, user_id: UUID, now: datetime) -> int:
    """Delete the person's traces older than the time a refusal is remembered."""
    gone = await session.scalars(
        delete(TRACE)
        .where(TRACE.user_id == user_id, TRACE.refused_at < now - REFUSAL_KEPT)
        .returning(TRACE.id)
    )
    return len(list(gone))


async def forget_everything(session: AsyncSession, user_id: UUID) -> None:
    """Delete every fact, trace and the summary of the person."""
    await session.execute(delete(FACT).where(FACT.user_id == user_id))
    await session.execute(delete(TRACE).where(TRACE.user_id == user_id))
    await session.execute(delete(MemorySummaryRecord).where(MemorySummaryRecord.user_id == user_id))


class Forgetting:
    """The hourly pass that deletes ended facts once they can no longer be taken back."""

    def __init__(
        self,
        transactions: HomeTransactions,
        metrics: MemoryMetrics,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._metrics = metrics
        self._clock = clock

    async def tidy(self, home: Home) -> int:
        """Delete the home's ended facts past their day; how many."""
        now, deleted = self._clock(), 0
        async for user_id in self._people(home, now - RESTORE_WINDOW):
            async with self._transactions.begin(TenancyScope(home, user_id)) as session:
                await session.execute(
                    select(func.pg_advisory_xact_lock(ADMISSION_LOCK_SPACE, person_key(user_id)))
                )
                deleted += await let_go(session, user_id, now)
        self._metrics.upkept(UpkeepPart.PURGED, deleted)
        return deleted

    async def _people(self, home: Home, cut: datetime) -> AsyncIterator[UUID]:
        """The people with ended facts past their day, through the sweep role, a batch at a time."""
        after: UUID | None = None
        while True:
            query = select(FACT.user_id).where(ended_before(cut)).distinct()
            if after is not None:
                query = query.where(FACT.user_id > after)
            async with self._transactions.begin(
                TenancyScope(home), read_only=True, sweep=True
            ) as session:
                found = list(await session.scalars(query.order_by(FACT.user_id).limit(BATCH)))
            for user_id in found:
                yield user_id
            if len(found) < BATCH:
                return
            after = found[-1]
