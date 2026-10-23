"""Giving held objects back to files once no attachment names them (ADR 0064 point 6).

The database's trigger names the held object of every deleted attachment in the deleting
transaction, so a cascade from a task, a board, an account or a workspace leaves none
behind. Tasks gives them back right after its own deletions commit and in a tick every 15
minutes; each owner's batch goes in the owner's transaction, which frees their storage, and
the objects no one names are deleted after its commit. A repeat finds nothing to give.
"""

from collections import defaultdict
from collections.abc import Collection
from datetime import timedelta
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.contracts.held_objects import HELD_OBJECTS
from shosai.features.tasks.infrastructure.attachment_records import TaskAttachmentReleaseRecord

RELEASES = TaskAttachmentReleaseRecord
BATCH: Final = 500
TICK_EVERY: Final = timedelta(minutes=15)
log = structlog.stdlib.get_logger(__name__)


class AttachmentReleases:
    """Gives the held objects of deleted attachments back to files."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def owner(self, scope: TenancyScope) -> int:
        """Give back what deletions in the scope left, right after their commit: the person's
        own, or the workspace's. How many went; a full batch leaves more for the next call."""
        conditions = (
            [RELEASES.user_id == scope.user_id, RELEASES.org_id.is_(None)]
            if scope.org_id is None
            else [RELEASES.org_id == scope.org_id]
        )
        async with self._transactions.begin(scope, read_only=True) as session:
            held_ids = list(
                await session.scalars(
                    select(RELEASES.held_object_id).where(*conditions).limit(BATCH)
                )
            )
        await self._give(scope, held_ids)
        return len(held_ids)

    async def drain(self, home: Home) -> int:
        """The tick: every owner's waiting batch; how many went."""
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rows = (
                await session.execute(
                    select(RELEASES.held_object_id, RELEASES.user_id, RELEASES.org_id)
                    .order_by(RELEASES.created_at)
                    .limit(BATCH)
                )
            ).all()
        owners: defaultdict[tuple[UUID, UUID | None], list[UUID]] = defaultdict(list)
        for held_id, user_id, org_id in rows:
            owners[user_id, org_id].append(held_id)
        for (user_id, org_id), held_ids in owners.items():
            await self._give(TenancyScope(home, user_id, org_id), held_ids)
        if rows:
            log.info(
                "Объекты удалённых вложений возвращены files", home=home.value, count=len(rows)
            )
        return len(rows)

    async def _give(self, scope: TenancyScope, held_ids: Collection[UUID]) -> None:
        if not held_ids:
            return
        held = self._ports.get(HELD_OBJECTS)
        async with self._transactions.begin(scope) as session:
            keys = await held.release(session, held_ids)
            await session.execute(
                delete(RELEASES).where(RELEASES.held_object_id.in_(list(held_ids)))
            )
        await held.discard(scope.home, keys)
