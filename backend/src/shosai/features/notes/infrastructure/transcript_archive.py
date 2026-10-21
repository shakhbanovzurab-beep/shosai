"""The transcript archive's storage: gzipped lines in a home's bucket and the guarded drop.

A meeting's lines are a few megabytes at most — six hours of speech — so an archive is put
and read whole; compressing and inflating run in a worker thread, off the event loop. A
month's partition goes only through the migration role's `notes_drop_archived_partition`,
which checks every meeting in it before the drop (plan step 20).
"""

import asyncio
import gzip
from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.homes import Home
from shosai.core.storage.port import ObjectStorage
from shosai.features.notes.domain.transcript_archive import ArchivedLine, decode_lines

ARCHIVE_TYPE: Final = "application/gzip"
READ_CHUNK: Final = 1024 * 1024


class PartitionDrop(StrEnum):
    """What the guarded drop did with a month's partition."""

    DROPPED = "dropped"
    ABSENT = "absent"
    UNARCHIVED = "unarchived"
    # Блокировку родителя не дали за 2 с: удаление повторит следующий такт.
    DEFERRED = "deferred"


class TranscriptArchive:
    """Archived lines in each home's bucket."""

    def __init__(self, objects: Mapping[Home, ObjectStorage]) -> None:
        self._objects = objects

    async def put(self, home: Home, key: str, lines: bytes) -> None:
        """Store a meeting's uncompressed lines under `key`, gzipped."""
        body = await asyncio.to_thread(gzip.compress, lines, mtime=0)
        await self._objects[home].put(key, body, content_type=ARCHIVE_TYPE)

    async def raw(self, home: Home, key: str) -> bytes:
        """A meeting's uncompressed lines as they were put."""
        async with self._objects[home].open(key) as stream:
            parts = [chunk async for chunk in stream.chunks(READ_CHUNK)]
        return await asyncio.to_thread(gzip.decompress, b"".join(parts))

    async def lines(self, home: Home, key: str) -> list[ArchivedLine]:
        """A meeting's archived lines in `seq` order."""
        return decode_lines(await self.raw(home, key))

    async def delete(self, home: Home, key: str) -> None:
        """Remove an archive no meeting points at."""
        await self._objects[home].delete(key)


async def drop_archived_month(session: AsyncSession, month: date) -> PartitionDrop:
    """Ask the owner's function to drop a month's partition; it refuses an unarchived one."""
    answer = await session.scalar(
        select(func.notes_drop_archived_partition(month.strftime("%Y%m")))
    )
    return PartitionDrop(str(answer))
