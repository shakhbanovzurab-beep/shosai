"""The `files.uploads` binding: a slice takes a ready upload in its own transaction.

The caller's transaction is the uploader's, in their home: row-level security shows only
their uploads. A ready, unexpired upload of the purpose becomes claimed; a File Manager
upload's reserved bytes become used in the same transaction. A second claim of the same
upload for the same purpose answers the same object; anything else is not claimable.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import transaction_info
from shosai.features.files.contracts import ClaimedObject, UploadNotClaimableError
from shosai.features.files.domain.purposes import PURPOSES, UploadPurpose
from shosai.features.files.domain.uploads import UploadState
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.upload_records import UploadRecord


class UploadClaims:
    """Ready uploads handed to the slice they are for."""

    def __init__(self, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._clock = clock

    async def claim(
        self, session: AsyncSession, upload_id: UUID, purpose: UploadPurpose
    ) -> ClaimedObject:
        """Take the session's person's ready upload of the purpose; the same on a repeat."""
        user_id = transaction_info(session).scope.user_id
        record = await session.scalar(
            select(UploadRecord)
            .where(UploadRecord.id == upload_id, UploadRecord.user_id == user_id)
            .with_for_update()
        )
        if record is None or record.purpose != purpose.value:
            raise UploadNotClaimableError
        if record.state == UploadState.READY.value and self._clock() < record.expires_at:
            record.state = UploadState.CLAIMED.value
            record.finished_at = self._clock()
            if PURPOSES[purpose].in_file_manager:
                await usage_store.settle(session, record.user_id, record.size_bytes)
        elif record.state != UploadState.CLAIMED.value:
            raise UploadNotClaimableError
        return ClaimedObject(
            upload_id=record.id,
            object_key=record.object_key,
            size_bytes=record.size_bytes,
            content_type=record.content_type,
            filename=record.filename,
        )
