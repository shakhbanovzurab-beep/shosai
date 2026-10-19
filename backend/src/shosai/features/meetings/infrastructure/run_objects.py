"""The transient objects of a meeting's runs: named for deletion with their rows, then deleted.

A run points at its recording, its raw recognition and its speaker turns in the home's
bucket. Whoever removes runs — the purge of a deleted meeting, an account's erasure —
names their keys in `meeting_object_deletions` in the transaction that removes the rows,
deletes the objects after that commit, and then forgets the keys; a deletion that fails
leaves its keys named for the next attempt.
"""

from collections.abc import Mapping, Sequence

from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.port import ObjectStorage
from shosai.features.meetings.infrastructure.run_records import ObjectDeletionRecord, RunRecord


async def run_keys(session: AsyncSession, where: ColumnElement[bool]) -> list[str]:
    """The transient keys named by the runs the predicate picks, each once, in order."""
    columns = (RunRecord.audio_key, RunRecord.raw_transcript_key, RunRecord.turns_key)
    rows = (await session.execute(select(*columns).where(where))).all()
    return sorted({key for row in rows for key in row if key})


async def record_deletions(session: AsyncSession, keys: Sequence[str]) -> None:
    """Name the keys for deletion in the transaction that removes their rows."""
    if keys:
        statement = insert(ObjectDeletionRecord).values([{"object_key": key} for key in keys])
        await session.execute(statement.on_conflict_do_nothing())


class RunObjects:
    """Deletes the named objects of each home and forgets them."""

    def __init__(
        self, transactions: HomeTransactions, objects: Mapping[Home, ObjectStorage]
    ) -> None:
        self._transactions = transactions
        self._objects = objects

    async def delete(self, home: Home, keys: Sequence[str]) -> None:
        """Delete the objects after their rows' commit, then forget them; a failure waits."""
        if not keys:
            return
        await self._objects[home].delete_many(list(keys))
        async with self._transactions.begin(TenancyScope(home)) as session:
            await session.execute(
                delete(ObjectDeletionRecord).where(ObjectDeletionRecord.object_key.in_(keys))
            )
