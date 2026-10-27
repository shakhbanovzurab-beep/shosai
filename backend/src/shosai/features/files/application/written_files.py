"""Files a recorder wrote straight into a person's storage, adopted into File Manager (A7 of
meetings; `contracts.written_files`).

The key is the person's file key for the id the writer was given (ADR 0055), so adopting is a
row and a charge: the File Manager file under that id, at the root, not used by Leo, its bytes
added to the person's used storage whatever the limit — the bytes exist already, and the quota
rules (FL-D2) act on a person over it — and `files.file.uploaded`. A repeat answers the file.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.contracts.events import FileUploaded
from shosai.features.files.contracts.written_files import WrittenFile
from shosai.features.files.domain.keys import PersonOwner, file_key
from shosai.features.files.domain.kinds import kind_of
from shosai.features.files.domain.quota import limit_bytes
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.usage_store import USAGE


class WrittenFilesService:
    """The `files.written_files` binding."""

    def __init__(
        self, transactions: HomeTransactions, ports: PortDirectory, outbox: EventOutbox
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._outbox = outbox

    def key_for(self, user_id: UUID, file_id: UUID) -> str:
        """The person's file key for the id."""
        return file_key(PersonOwner(user_id), file_id)

    async def bytes_left(self, home: Home, user_id: UUID) -> int | None:
        """The person's free storage by their plan; None when unlimited."""
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(home, user_id)
        limit = limit_bytes(snapshot.limits.file_manager_gb)
        if limit is None:
            return None
        async with self._transactions.begin(TenancyScope(home, user_id), read_only=True) as session:
            row = (
                await session.execute(
                    select(USAGE.used_bytes, USAGE.reserved_bytes).where(USAGE.user_id == user_id)
                )
            ).first()
        used = 0 if row is None else row.used_bytes + row.reserved_bytes
        return max(0, limit - used)

    async def adopt(self, session: AsyncSession, written: WrittenFile) -> UUID:
        """The object as the person's file; the same file on a repeat."""
        existing = await session.get(StorageFileRecord, written.file_id)
        if existing is not None:
            return existing.id
        now = datetime.now(UTC)
        session.add(
            StorageFileRecord(
                id=written.file_id, user_id=written.user_id, name=written.name,
                content_type=written.content_type, size_bytes=written.size_bytes,
                object_key=self.key_for(written.user_id, written.file_id),
                created_at=now, modified_at=now,
            )
        )  # fmt: skip
        await session.flush()
        await usage_store.add_used(session, written.user_id, written.size_bytes)
        await self._outbox.add(
            session,
            FileUploaded(
                file_id=written.file_id, user_id=written.user_id,
                size_bytes=written.size_bytes, kind=kind_of(written.name).value,
            ),
        )  # fmt: skip
        return written.file_id
