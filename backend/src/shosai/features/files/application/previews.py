"""Making the previews of held images (ADR 0064 point 5).

The sweep role finds the held object; its bytes are read and decoded outside any
transaction, in a thread; the preview is written under the owner's prefix and named on the
row in the owner's transaction while the row still waits for it. A preview made for a row
released meanwhile is named by nobody and goes at once. Previews still to make after ten
minutes — a delivery lost to an unreachable queue — are queued again by the upload sweep.
"""

import asyncio
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import select, update

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.port import ObjectStorage
from shosai.features.files.application.account_data import unnamed
from shosai.features.files.application.preview_task import (
    MAKE_PREVIEW,
    PreviewPayload,
    PreviewSender,
)
from shosai.features.files.domain.keys import PersonOwner, WorkspaceOwner, preview_key
from shosai.features.files.domain.previews import PREVIEW_TYPE, SOURCE_MAX_BYTES
from shosai.features.files.infrastructure.held_records import HeldObjectRecord
from shosai.features.files.infrastructure.image_previews import PreviewRefusedError, webp_preview
from shosai.features.files.infrastructure.object_deleter import ObjectDeleter, record_deletions

CHUNK_BYTES: Final = 1024 * 1024
RETRY_AFTER: Final = timedelta(minutes=10)
RETRY_BATCH: Final = 100
log = structlog.stdlib.get_logger(__name__)


class Previews:
    """Makes previews of held images and queues again the ones left to make."""

    def __init__(
        self,
        transactions: HomeTransactions,
        storage: tuple[Mapping[Home, ObjectStorage], ObjectDeleter],
        tasks: PreviewSender,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._objects, self._deleter = storage
        self._tasks = tasks
        self._clock = clock

    async def make(self, home: Home, held_id: UUID) -> None:
        """The held image's preview, once; a row released or done meanwhile is left be."""
        record = await self._waiting(home, held_id)
        if record is None:
            return
        owner = (
            PersonOwner(record.user_id) if record.org_id is None else WorkspaceOwner(record.org_id)
        )
        scope = TenancyScope(home, record.user_id, record.org_id)
        try:
            source = await self._bytes(home, record)
            preview = await asyncio.to_thread(webp_preview, source)
        except PreviewRefusedError:
            log.info("Превью не сделано: картинка не читается", home=home.value)
            await self._finish(scope, held_id, None)
            return
        key = preview_key(owner, held_id)
        await self._objects[home].put(key, preview, content_type=PREVIEW_TYPE)
        if not await self._finish(scope, held_id, key):
            async with self._transactions.begin(scope) as session:
                orphaned = await unnamed(session, [key])
                await record_deletions(session, orphaned)
            await self._deleter.discard(home, orphaned)

    async def retry(self, home: Home) -> int:
        """Queue again the previews still to make after ten minutes; how many went."""
        due = (
            select(HeldObjectRecord.id)
            .where(
                HeldObjectRecord.preview_state == "pending",
                HeldObjectRecord.created_at <= self._clock() - RETRY_AFTER,
            )
            .order_by(HeldObjectRecord.created_at)
            .limit(RETRY_BATCH)
        )
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            held_ids = list(await session.scalars(due))
        for held_id in held_ids:
            await self._tasks.send(MAKE_PREVIEW, PreviewPayload(home=home, held_id=held_id))
        return len(held_ids)

    async def _waiting(self, home: Home, held_id: UUID) -> HeldObjectRecord | None:
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            return await session.scalar(
                select(HeldObjectRecord).where(
                    HeldObjectRecord.id == held_id, HeldObjectRecord.preview_state == "pending"
                )
            )

    async def _bytes(self, home: Home, record: HeldObjectRecord) -> bytes:
        if record.size_bytes > SOURCE_MAX_BYTES:
            raise PreviewRefusedError
        async with self._objects[home].open(record.object_key) as stream:
            return b"".join([chunk async for chunk in stream.chunks(CHUNK_BYTES)])

    async def _finish(self, scope: TenancyScope, held_id: UUID, key: str | None) -> bool:
        """Name the preview, or mark it failed; False when the row no longer waits for it."""
        async with self._transactions.begin(scope) as session:
            done = await session.scalar(
                update(HeldObjectRecord)
                .where(HeldObjectRecord.id == held_id, HeldObjectRecord.preview_state == "pending")
                .values(preview_key=key, preview_state="failed" if key is None else "made")
                .returning(HeldObjectRecord.id)
            )
        return done is not None
