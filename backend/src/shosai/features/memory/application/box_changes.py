"""What a message in the "Ask or update" box changes, applied (memory step 7, MM-D3).

In one transaction under the person's admission lock, with the switch read again inside it: a
statement to remember becomes the person's own confirmed fact in Personal, unless the same
words are already held; a correction supersedes the fact — the person's edit takes its place
in the fact's space; a forget ends it. Only facts still current change. Each change names the
fact the person sees now and, for a correction, the one it replaced, so the dialog can undo it:
a remembered fact is forgotten, a corrected or forgotten one restored, for a day.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.ids import new_id
from shosai.features.memory.application.admission_writer import ADMISSION_LOCK_SPACE, person_key
from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.fact_rows import (
    FACT,
    fact_of,
    successor_row,
    visible,
    write_back,
)
from shosai.features.memory.application.switch import memory_on
from shosai.features.memory.domain.admission import same_words
from shosai.features.memory.domain.box import BoxPlan, Correction, NewStatement
from shosai.features.memory.domain.facts import (
    EndReason,
    Fact,
    FactStatus,
    MemorySource,
    forget,
    supersede,
)
from shosai.features.memory.infrastructure.records import MemoryFactRecord


class ChangeKind(StrEnum):
    """What a message did to a fact."""

    REMEMBERED = "remembered"
    UPDATED = "updated"
    FORGOTTEN = "forgotten"


@dataclass(frozen=True, slots=True)
class Change:
    """One fact the message changed, and the one a correction replaced."""

    change: ChangeKind
    fact_id: UUID
    replaced_id: UUID | None = None


class BoxChanges:
    """Applies a message's plan in the person's transaction."""

    def __init__(self, lists: FactLists, clock: Callable[[], datetime]) -> None:
        self._lists = lists
        self._clock = clock

    async def apply(self, session: AsyncSession, user_id: UUID, plan: BoxPlan) -> list[Change]:
        """The changes made; None of them when memory is off by now."""
        await session.execute(
            select(func.pg_advisory_xact_lock(ADMISSION_LOCK_SPACE, person_key(user_id)))
        )
        if not await memory_on(session, user_id):
            return []
        now = self._clock()
        spaces = await self._lists.spaces(session, user_id)
        named = {*plan.forget, *(correction.fact_id for correction in plan.update)}
        current = await self._targets(session, visible(user_id, spaces), named)
        changes: list[Change] = []
        for fact_id in plan.forget:
            row = current.get(fact_id)
            if row is not None:
                write_back(row, forget(fact_of(row), EndReason.FORGOT, now), now)
                changes.append(Change(ChangeKind.FORGOTTEN, row.id))
        for correction in plan.update:
            changed = self._correct(session, current.get(correction.fact_id), correction, now)
            if changed is not None:
                changes.append(changed)
        held = list(
            await session.scalars(
                select(FACT.statement).where(
                    visible(user_id, spaces), FACT.status == FactStatus.ACTIVE.value
                )
            )
        )
        for item in plan.remember:
            if not any(same_words(item.statement, statement) for statement in held):
                fact_id = self._remember(session, user_id, item, now)
                changes.append(Change(ChangeKind.REMEMBERED, fact_id))
                held.append(item.statement)
        await session.flush()
        return changes

    @staticmethod
    async def _targets(
        session: AsyncSession, seen: ColumnElement[bool], named: set[UUID]
    ) -> dict[UUID, MemoryFactRecord]:
        """The named facts still current, locked."""
        if not named:
            return {}
        rows = await session.scalars(
            select(FACT)
            .where(FACT.id.in_(tuple(named)), seen, FACT.status == FactStatus.ACTIVE.value)
            .with_for_update()
        )
        return {row.id: row for row in rows}

    @staticmethod
    def _correct(
        session: AsyncSession,
        row: MemoryFactRecord | None,
        correction: Correction,
        now: datetime,
    ) -> Change | None:
        if row is None or not fact_of(row).current:
            return None
        old = fact_of(row)
        if correction.statement == old.statement:
            return None
        successor = Fact(
            id=new_id(), kind=old.kind, statement=correction.statement, status=FactStatus.ACTIVE,
            source=MemorySource.USER_EDIT, created_at=now, last_confirmed_at=now, explicit=True,
            confirmed=True, confirmations=old.confirmations + 1,
        )  # fmt: skip
        closed, opened = supersede(old, successor, now)
        write_back(row, closed, now)
        session.add(successor_row(row, opened, now))
        return Change(ChangeKind.UPDATED, opened.id, old.id)

    @staticmethod
    def _remember(session: AsyncSession, user_id: UUID, item: NewStatement, now: datetime) -> UUID:
        fact_id = new_id()
        session.add(
            MemoryFactRecord(
                id=fact_id, user_id=user_id, org_id=None, kind=item.kind.value,
                statement=item.statement, source_kind=MemorySource.SETTINGS.value, source_ref={},
                confidence=1.0, explicit=True, confirmed=True, status=FactStatus.ACTIVE.value,
                confirmations=1, last_confirmed_at=now, valid_from=now, created_at=now,
                updated_at=now,
            )
        )  # fmt: skip
        return fact_id
