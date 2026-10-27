"""A fact follows its source (memory step 8, ADR 0071 MM-D4).

Reads already hide a fact of a workspace the person is no longer in, and a fact marked
`erase_after`. `workspaces.member.removed` marks the person's facts of that workspace seven days
on, as the departed person — a later departure moves the mark later, never earlier — and a
member again by the delivery is left as they are; a deleted workspace's facts go at once.
`notes.meeting.deleted` marks every person's facts of the meeting for the day notes purges it,
and `notes.meeting.restored` lifts the marks of those who may read it again. The hourly
settling decides each due mark by what holds then: a fact of a workspace the person is not in,
or of a meeting they can no longer read, is erased; any other is back.
"""

from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import ColumnElement, Row, and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.memory.application.fact_rows import FACT
from shosai.features.memory.domain.facts import MemorySource
from shosai.features.memory.domain.lifetimes import (
    erase_after_departure,
    erase_after_meeting_deleted,
)
from shosai.features.memory.infrastructure.metrics import MemoryMetrics, UpkeepPart
from shosai.features.notes.contracts import MEETING_READER
from shosai.features.workspaces.contracts import MEMBERSHIP_READER, Viewer

# Людей за одно чтение роли обходов; следующие — после последнего прочитанного.
BATCH: Final = 500
log = structlog.stdlib.get_logger(__name__)


def of_meeting(meeting_id: UUID) -> ColumnElement[bool]:
    """A fact a meeting's recollection gave."""
    return and_(
        FACT.source_kind == MemorySource.MEETING.value,
        FACT.source_ref["meeting_id"].astext == str(meeting_id),
    )


def later_mark(due: datetime) -> ColumnElement[datetime]:
    """The mark moved to `due` unless it is already later."""
    return func.greatest(func.coalesce(FACT.erase_after, due), due)


class Departures:
    """Marks, erasures and the settling of marks."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, MemoryMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._metrics = collaborators
        self._clock = clock

    async def left(self, session: AsyncSession, user_id: UUID, org_id: UUID, at: datetime) -> None:
        """Mark the person's facts of the workspace they left, unless they are back."""
        if await self._member(session, user_id, org_id):
            log.info("Участник снова в пространстве: факты памяти не помечены", org_id=str(org_id))
            return
        await session.execute(
            update(FACT)
            .where(FACT.user_id == user_id, FACT.org_id == org_id)
            .values(erase_after=later_mark(erase_after_departure(at)))
        )

    async def workspace_deleted(self, home: Home, org_id: UUID) -> int:
        """Erase every fact of a deleted workspace, person by person; how many went."""
        erased = 0
        async for user_id in self._people(home, FACT.org_id == org_id):
            async with self._transactions.begin(TenancyScope(home, user_id)) as session:
                gone = await session.scalars(
                    delete(FACT)
                    .where(FACT.user_id == user_id, FACT.org_id == org_id)
                    .returning(FACT.id)
                )
                erased += len(list(gone))
        self._metrics.upkept(UpkeepPart.ERASED, erased)
        return erased

    async def meeting_deleted(self, home: Home, meeting_id: UUID, at: datetime) -> None:
        """Mark every person's facts of the meeting for the day notes purges it."""
        due = erase_after_meeting_deleted(at)
        async for user_id in self._people(home, of_meeting(meeting_id)):
            async with self._transactions.begin(TenancyScope(home, user_id)) as session:
                await session.execute(
                    update(FACT)
                    .where(FACT.user_id == user_id, of_meeting(meeting_id))
                    .values(erase_after=later_mark(due))
                )

    async def meeting_restored(self, home: Home, meeting_id: UUID) -> None:
        """Settle the marks of a restored meeting's facts now: back where they may be read."""
        async for user_id in self._people(home, of_meeting(meeting_id)):
            await self._settle(TenancyScope(home, user_id), of_meeting(meeting_id), None)

    async def settle(self, home: Home) -> None:
        """Decide the marks that are due: erase or bring back."""
        now = self._clock()
        due = (FACT.erase_after.is_not(None)) & (FACT.erase_after <= now)
        async for user_id in self._people(home, due):
            await self._settle(TenancyScope(home, user_id), due, now)

    async def _settle(
        self, scope: TenancyScope, which: ColumnElement[bool], now: datetime | None
    ) -> None:
        """Erase the person's marked facts they may no longer have, lift the others' marks;
        `now` None — a restore: lift the marks it may and erase nothing yet."""
        user_id = scope.user_id
        if user_id is None:
            return
        async with self._transactions.begin(scope) as session:
            rows = (
                await session.execute(
                    select(FACT.id, FACT.org_id, FACT.source_kind, FACT.source_ref)
                    .where(FACT.user_id == user_id, FACT.erase_after.is_not(None), which)
                    .with_for_update()
                )
            ).all()
            gone = await self._lost(session, user_id, rows)
            back = [row[0] for row in rows if row[0] not in gone]
            if gone and now is not None:
                await session.execute(delete(FACT).where(FACT.id.in_(gone)))
            if back:
                await session.execute(
                    update(FACT).where(FACT.id.in_(back)).values(erase_after=None)
                )
        self._metrics.upkept(UpkeepPart.ERASED, len(gone) if now is not None else 0)
        self._metrics.upkept(UpkeepPart.RESTORED, len(back))

    async def _lost(
        self,
        session: AsyncSession,
        user_id: UUID,
        rows: Sequence[Row[UUID, UUID | None, str, dict[str, str]]],
    ) -> set[UUID]:
        """The facts whose source the person no longer has: a workspace left, a meeting gone."""
        memberships = await self._ports.get(MEMBERSHIP_READER).active(session, user_id)
        spaces = {membership.org_id for membership in memberships}
        meetings = {
            UUID(ref["meeting_id"])
            for _, _, kind, ref in rows
            if kind == MemorySource.MEETING.value and ref.get("meeting_id")
        }
        readable = await self._ports.get(MEETING_READER).readable(
            session, Viewer(user_id), meetings
        )
        return {
            fact_id
            for fact_id, org_id, kind, ref in rows
            if (org_id is not None and org_id not in spaces)
            or (kind == MemorySource.MEETING.value and UUID(ref["meeting_id"]) not in readable)
        }

    async def _people(self, home: Home, which: ColumnElement[bool]) -> AsyncIterator[UUID]:
        """The people who have such facts, through the sweep role, a batch at a time."""
        after: UUID | None = None
        while True:
            query = select(FACT.user_id).where(which).distinct().order_by(FACT.user_id)
            if after is not None:
                query = query.where(FACT.user_id > after)
            async with self._transactions.begin(
                TenancyScope(home), read_only=True, sweep=True
            ) as session:
                found = list(await session.scalars(query.limit(BATCH)))
            for user_id in found:
                yield user_id
            if len(found) < BATCH:
                return
            after = found[-1]

    async def _member(self, session: AsyncSession, user_id: UUID, org_id: UUID) -> bool:
        members = await self._ports.get(MEMBERSHIP_READER).members(session, org_id, [user_id])
        return user_id in members
