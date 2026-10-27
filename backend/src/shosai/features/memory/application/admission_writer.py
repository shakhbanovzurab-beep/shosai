"""Writing what a turn's or a meeting's statements became, under the person's lock (steps 5, 9).

Each statement's nearest facts — current, waiting, and those the person forgot or turned down
in the last 180 days — are read with the statement's vector, the rules decide, and the result
is written in one transaction that holds the person's admission lock, so two turns never
count the same day's candidates twice. The switch is read again inside it: a fact is never
written after the person turned memory off (§16.4).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class Origin:
    """Where statements were said: the source, its space, its references, the conversation
    a turn's came from, the taint of what was read and when it was said."""

    source: MemorySource
    org_id: UUID | None
    refs: Mapping[str, str]
    taint: Taint
    said_at: datetime
    thread_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class Found:
    """A statement, its vector, and the references of its own evidence."""

    statement: Statement
    vector: Sequence[float]
    refs: Mapping[str, str] = field(default_factory=dict)


def turn_origin(words: TurnWords) -> Origin:
    """A turn's statements: the person's own words in their conversation."""
    return Origin(
        source=MemorySource.USER_STATEMENT,
        org_id=words.org_id,
        refs={"thread_id": str(words.thread_id), "message_id": str(words.message_id)},
        taint=words.taint,
        said_at=words.said_at,
        thread_id=words.thread_id,
    )


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
        origin: Origin,
        found: Sequence[Found],
    ) -> list[Admission]:
        """What each statement became; nothing at all when memory is off by now."""
        await session.execute(
            select(func.pg_advisory_xact_lock(ADMISSION_LOCK_SPACE, person_key(user_id)))
        )
        if not await memory_on(session, user_id):
            return []
        now = self._clock()
        outcomes: list[Admission] = []
        for item in found:
            near = await self._neighbours(session, user_id, item.vector, now)
            today = await self._candidates_today(session, user_id, now)
            admit = before_judge(item.statement, origin.source, near, now) or by_rule(
                item.statement, origin.source, today, subject_fact(near)
            )
            await self._apply(session, (user_id, origin, now), item, admit)
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
        where: tuple[UUID, Origin, datetime],
        item: Found,
        admit: Admit,
    ) -> None:
        user_id, origin, now = where
        statement = item.statement
        if admit.admission is Admission.CONFIRMED and admit.neighbour is not None:
            held = await session.get(MemoryFactRecord, admit.neighbour, with_for_update=True)
            if held is not None and fact_of(held).current:
                write_back(held, confirm_again(fact_of(held), now), now)
            return
        if not admit.writes:
            return
        session.add(
            MemoryFactRecord(
                id=new_id(), user_id=user_id, org_id=origin.org_id, kind=statement.kind.value,
                statement=statement.text, source_kind=origin.source.value,
                source_ref={**origin.refs, **item.refs}, thread_id=origin.thread_id,
                confidence=1.0 if admit.confirmed else 0.5,
                sensitivity=sensitivity_of(statement).value,
                explicit=statement.explicit, confirmed=admit.confirmed,
                source_taint=TAINTS[min(origin.taint, Taint.EXTERNAL)],
                status=(FactStatus.ACTIVE if admit.confirmed else FactStatus.CANDIDATE).value,
                replaces=admit.neighbour, confirmations=1 if admit.confirmed else 0,
                last_confirmed_at=now, embedding=list(item.vector), embedding_model=self._model,
                valid_from=origin.said_at, created_at=now, updated_at=now,
            )
        )  # fmt: skip
