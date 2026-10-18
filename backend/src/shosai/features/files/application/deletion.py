"""A file's deletion (FL-D5): hidden from everyone at once, out of the quota, announced.

The person's own delete and the removal after FL-D2's 90 days take this one path, in the
owner's transaction; the purge removes the row 7 days later.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.features.files.contracts.events import FileDeleted
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.file_records import StorageFileRecord


async def hide_file(
    session: AsyncSession, outbox: EventOutbox, record: StorageFileRecord, now: datetime
) -> None:
    """Hide a locked, visible file of a person, free its bytes and tell those who used it."""
    record.deleted_at = now
    await usage_store.free(session, record.user_id, record.size_bytes)
    await outbox.add(session, FileDeleted(file_id=record.id, user_id=record.user_id))
