"""Writing what a turn's statements became, under the person's lock (memory step 5).

Each statement's nearest facts — current, waiting, and those the person forgot or turned down
in the last 180 days — are read with the statement's vector, the rules decide, and the result
is written in one transaction that holds the person's admission lock, so two turns never
count the same day's candidates twice. The switch is read again inside it: a fact is never
written after the person turned memory off (§16.4).
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import Taint
from shosai.core.kernel.ids import new_id
from shosai.features.agent.contracts.memory import TurnWords
from shosai.features.memory.application.fact_rows import FACT, TAINTS, fact_of, write_back
from shosai.features.memory.application.switch import memory_on
from shosai.features.memory.domain.admission import (
    NEIGHBOURS,
    REFUSALS,
    REFUSALS_REMEMBERED,
    Admission,
    Admit,
    Neighbour,
    Statement,
    before_judge,
    by_rule,
    subject_fact,
)
from shosai.features.memory.domain.facts import (
    EndReason,
    FactStatus,
    MemorySource,
    Sensitivity,
    confirm_again,
)
from shosai.features.memory.infrastructure.records import MemoryFactRecord, MemorySummaryRecord

# Пространство ключей блокировок приёма памяти (ASCII «Mem»); второй ключ — id человека.
ADMISSION_LOCK_SPACE: Final = 0x4D656D
WORD: Final = 2**32
DAY: Final = timedelta(days=1)


def person_key(user_id: UUID) -> int:
    """The person's half of the lock's key: the id folded into a signed 32-bit integer."""
    folded = user_id.int
    folded ^= folded >> 64
    folded ^= folded >> 32
    folded %= WORD
    return folded - WORD if folded >= WORD // 2 else folded


def sensitivity_of(statement: Statement) -> Sensitivity:
    """How personal the statement is."""
    return Sensitivity.SENSITIVE if statement.sensitive else Sensitivity.NORMAL


class AdmissionWriter:
    """Decides and writes a turn's statements in the person's transaction."""

    def __init__(
        self, model: str, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._model = model
        self._clock = clock

    async def write(
        self,
        session: AsyncSession,
        user_id: UUID,
        words: TurnWords,
        found: Sequence[tuple[Statement, Sequence[float]]],
    ) -> list[Admission]:
        """What each statement became; nothing at all when memory is off by now."""
        await session.execute(
            select(func.pg_advisory_xact_lock(ADMISSION_LOCK_SPACE, person_key(user_id)))
        )
        if not await memory_on(session, user_id):
            return []
        now = self._clock()
        outcomes: list[Admission] = []
        for statement, vector in found:
            near = await self._neighbours(session, user_id, vector, now)
            today = await self._candidates_today(session, user_id, now)
            admit = before_judge(statement, MemorySource.USER_STATEMENT, near, now) or by_rule(
                statement, MemorySource.USER_STATEMENT, today, subject_fact(near)
            )
            await self._apply(session, (user_id, words, now), (statement, vector), admit)
            outcomes.append(admit.admission)
        if any(outcome in {Admission.ACTIVE, Admission.CANDIDATE} for outcome in outcomes):
            await session.execute(
                update(MemorySummaryRecord)
                .where(MemorySummaryRecord.user_id == user_id)
                .values(stale=True)
            )
        return outcomes

    async def _neighbours(
        self, session: AsyncSession, user_id: UUID, vector: Sequence[float], now: datetime
    ) -> list[Neighbour]:
        distance = FACT.embedding.cosine_distance(vector)
        alive = and_(
            FACT.status.in_((FactStatus.ACTIVE.value, FactStatus.CANDIDATE.value)),
            FACT.valid_to.is_(None),
        )
        refused = and_(
            FACT.status == FactStatus.FORGOTTEN.value,
            FACT.ended_reason.in_(tuple(reason.value for reason in REFUSALS)),
            FACT.ended_at >= now - REFUSALS_REMEMBERED,
        )
        rows = (
            await session.execute(
                select(FACT, distance)
                .where(FACT.user_id == user_id, FACT.embedding_model == self._model)
                .where(or_(alive, refused))
                .order_by(distance)
                .limit(NEIGHBOURS)
            )
        ).all()
        return [Neighbour(fact_of(row), 1 - float(gap)) for row, gap in rows]

    @staticmethod
    async def _candidates_today(session: AsyncSession, user_id: UUID, now: datetime) -> int:
        """Candidates asked in the last day — waiting, accepted or turned down since — the
        draft's carried-over ones aside; a fact saved without asking is not one."""
        asked = or_(
            FACT.status == FactStatus.CANDIDATE.value,
            FACT.confirmed.is_(True),
            FACT.ended_reason == EndReason.TURNED_DOWN.value,
        )
        count = await session.scalar(
            select(func.count())
            .select_from(FACT)
            .where(
                FACT.user_id == user_id,
                FACT.created_at >= now - DAY,
                FACT.source_kind != MemorySource.IMPORTED.value,
                FACT.explicit.is_(False),
                asked,
            )
        )
        return int(count or 0)

    async def _apply(
        self,
        session: AsyncSession,
        where: tuple[UUID, TurnWords, datetime],
        what: tuple[Statement, Sequence[float]],
        admit: Admit,
    ) -> None:
        user_id, words, now = where
        statement, vector = what
        if admit.admission is Admission.CONFIRMED and admit.neighbour is not None:
            held = await session.get(MemoryFactRecord, admit.neighbour, with_for_update=True)
            if held is not None and fact_of(held).current:
                write_back(held, confirm_again(fact_of(held), now), now)
            return
        if not admit.writes:
            return
        session.add(
            MemoryFactRecord(
                id=new_id(), user_id=user_id, org_id=words.org_id, kind=statement.kind.value,
                statement=statement.text, source_kind=MemorySource.USER_STATEMENT.value,
                source_ref={"thread_id": str(words.thread_id), "message_id": str(words.message_id)},
                thread_id=words.thread_id, confidence=1.0 if admit.confirmed else 0.5,
                sensitivity=sensitivity_of(statement).value,
                explicit=statement.explicit, confirmed=admit.confirmed,
                source_taint=TAINTS[min(words.taint, Taint.EXTERNAL)],
                status=(FactStatus.ACTIVE if admit.confirmed else FactStatus.CANDIDATE).value,
                replaces=admit.neighbour, confirmations=1 if admit.confirmed else 0,
                last_confirmed_at=now, embedding=list(vector), embedding_model=self._model,
                valid_from=words.said_at, created_at=now, updated_at=now,
            )
        )  # fmt: skip
