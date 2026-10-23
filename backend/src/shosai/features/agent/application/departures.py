"""A workspace's threads follow the person's membership (AG-D3; agent plan §3.5 flow 5, step 4).

Reads hide a departed workspace's threads at once. `workspaces.member.removed` marks them
`erase_after` seven days after the departure, as the departed person (ADR 0067): a later
departure moves the mark later, never earlier, and a member active again by the delivery is
left as they are. The hourly purge takes the marks that are due: a person active there again
keeps the threads and loses the mark, anyone else loses the threads. A deleted workspace's
threads go at once: the sweep role lists the people who have some, and each person's go in
their own transaction, so a repeated delivery finds nothing left.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.threads import erase_threads
from shosai.features.agent.domain.threads import Erasure, erase_after, erasure
from shosai.features.agent.infrastructure.thread_records import AgentThreadRecord
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from shosai.features.workspaces.contracts.events import MemberRemoved

THREAD = AgentThreadRecord
# Пар «человек — пространство» за проход; остальные — в следующий час.
BATCH: Final = 500
log = structlog.stdlib.get_logger(__name__)


def scope_of_departure(event: MemberRemoved, scope: TenancyScope) -> TenancyScope:
    """The departed person in the workspace they left, in the event's home."""
    return TenancyScope(scope.home, event.user_id, event.org_id)


class Departures:
    """Marks, purges and erasures of the threads of workspaces a person no longer belongs to."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._clock = clock

    async def follow(
        self, session: AsyncSession, removed: MemberRemoved, departed_at: datetime
    ) -> None:
        """Mark the departed person's threads of the workspace to be erased in 7 days."""
        person, org_id = removed.user_id, removed.org_id
        if await self._member(session, person, org_id):
            log.info("Участник снова в пространстве: треды Leo не помечены", org_id=str(org_id))
            return
        due = erase_after(departed_at)
        await session.execute(
            update(THREAD)
            .where(THREAD.user_id == person, THREAD.org_id == org_id)
            .values(erase_after=func.greatest(func.coalesce(THREAD.erase_after, due), due))
        )

    async def purge(self, home: Home) -> int:
        """Settle the marks that are due: erase or restore; how many threads went."""
        now = self._clock()
        due = (
            select(THREAD.user_id, THREAD.org_id)
            .where(THREAD.erase_after <= now)
            .group_by(THREAD.user_id, THREAD.org_id)
            .limit(BATCH)
        )
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            pairs = (await session.execute(due)).all()
        erased = 0
        for user_id, org_id in pairs:
            erased += await self._settle(TenancyScope(home, user_id, org_id), now)
        if erased:
            log.info("Треды Leo ушедших из пространств стёрты", home=home.value, threads=erased)
        return erased

    async def erase_workspace(self, home: Home, org_id: UUID) -> int:
        """Erase every thread of a deleted workspace, person by person; how many went."""
        people = select(THREAD.user_id).where(THREAD.org_id == org_id).distinct()
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            user_ids = list(await session.scalars(people))
        erased = 0
        for user_id in user_ids:
            async with self._transactions.begin(TenancyScope(home, user_id)) as session:
                ids = await session.scalars(
                    select(THREAD.id).where(THREAD.user_id == user_id, THREAD.org_id == org_id)
                )
                erased += await erase_threads(session, user_id, ids.all())
        if erased:
            log.info("Треды Leo удалённого пространства стёрты", org_id=str(org_id), threads=erased)
        return erased

    async def _settle(self, scope: TenancyScope, now: datetime) -> int:
        user_id, org_id = scope.user_id, scope.org_id
        if user_id is None or org_id is None:
            message = "отметка треда снимается от имени человека в пространстве"
            raise ValueError(message)
        async with self._transactions.begin(scope) as session:
            member_again = await self._member(session, user_id, org_id)
            marked = (
                await session.execute(
                    select(THREAD.id, THREAD.erase_after)
                    .where(
                        THREAD.user_id == user_id,
                        THREAD.org_id == org_id,
                        THREAD.erase_after.is_not(None),
                    )
                    .with_for_update()
                )
            ).all()
            verdicts = {
                thread_id: erasure(due, now, member_again=member_again)
                for thread_id, due in marked
                if due is not None
            }
            restored = [key for key, verdict in verdicts.items() if verdict is Erasure.RESTORED]
            if restored:
                await session.execute(
                    update(THREAD).where(THREAD.id.in_(restored)).values(erase_after=None)
                )
            gone = [key for key, verdict in verdicts.items() if verdict is Erasure.ERASE]
            return await erase_threads(session, user_id, gone)

    async def _member(self, session: AsyncSession, user_id: UUID, org_id: UUID) -> bool:
        members = await self._ports.get(MEMBERSHIP_READER).members(session, org_id, [user_id])
        return user_id in members
