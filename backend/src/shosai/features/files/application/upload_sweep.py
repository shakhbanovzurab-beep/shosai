"""The sweep of uploads past their 24 hours, and of objects waiting for deletion (§10).

The sweep role only lists what is due across people; each upload is then closed in its
owner's transaction by the same conditional update a completion uses, so a late
completion and the sweep never both win. A pending upload's multipart upload is aborted
first, outside any transaction, a File Manager upload's bytes are released, and a ready
upload's object joins the deletions. The bucket rule aborts the same uploads after 24
hours, so the sweep and the rule agree.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Final

import structlog
from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.errors import StorageUnavailableError
from shosai.core.storage.port import MultipartUpload, MultipartUploads
from shosai.features.files.application.uploads import move_state
from shosai.features.files.domain.purposes import PURPOSES, UploadPurpose
from shosai.features.files.domain.uploads import UploadState
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.object_deleter import ObjectDeleter, record_deletions
from shosai.features.files.infrastructure.upload_records import UploadRecord

# Загрузок за один проход очистки.
BATCH: Final = 500

log = structlog.stdlib.get_logger(__name__)


class UploadSweep:
    """Closes expired uploads and retries pending object deletions in a home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        storage: tuple[Mapping[Home, MultipartUploads], ObjectDeleter],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._uploads, self._deleter = storage
        self._clock = clock

    async def run(self, home: Home) -> int:
        """One pass in a home; how many uploads it closed."""
        due = select(UploadRecord).where(
            UploadRecord.state.in_((UploadState.PENDING.value, UploadState.READY.value)),
            UploadRecord.expires_at <= self._clock(),
        )
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            records = list(
                await session.scalars(due.order_by(UploadRecord.expires_at).limit(BATCH))
            )
        closed = 0
        for record in records:
            closed += await self._expire(home, record)
        await self._deleter.retry(home)
        return closed

    async def _expire(self, home: Home, record: UploadRecord) -> int:
        state = UploadState(record.state)
        if state is UploadState.PENDING:
            try:
                await self._uploads[home].abort(
                    MultipartUpload(record.object_key, record.multipart_id)
                )
            except StorageUnavailableError:
                log.warning("Загрузка не отменена: бакет недоступен", home=home.value)
                return 0
        scope = TenancyScope(home, record.user_id)
        async with self._transactions.begin(scope) as session:
            moved = await move_state(session, record.id, state, UploadState.EXPIRED)
            if moved is not None:
                if PURPOSES[UploadPurpose(record.purpose)].counted:
                    await usage_store.release(session, record.user_id, record.size_bytes)
                await record_deletions(session, [record.object_key])
        if moved is None:
            return 0
        await self._deleter.discard(home, [record.object_key])
        return 1
