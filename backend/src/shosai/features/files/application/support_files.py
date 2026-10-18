"""Support's view of a person's deleted files and their restore (FL-D5, ADR 0045 point 6).

Support reads a person's files deleted within 7 days in the person's home and restores
one: it comes back into the quota (passing the limit starts FL-D2's 90 days), is shared
nowhere, and Leo uses it again if its switch or its folder's says so — like the quota, the
knowledge limit does not refuse support's restore; passing it starts FL-D10's 90 days.
While the account is in identity's deletion window support neither sees nor restores its
files (409 `account_deletion_scheduled`): only cancelling the deletion brings them back.
Every list and every restore goes to the admin's EU audit log through identity's port, in
the same transaction.
"""

from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.account_data.handlers import AccountRef
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.application.leo_use import LeoUse, candidate, unused
from shosai.features.files.application.leo_watch import LeoWatch
from shosai.features.files.application.quota_watch import QuotaWatch
from shosai.features.files.contracts.events import FileRestored
from shosai.features.files.domain.leo import LeoShift
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.file_records import FileFolderRecord, StorageFileRecord
from shosai.features.identity.contracts import OPERATOR_AUDIT, OperatorAction


@dataclass(frozen=True, slots=True)
class HiddenFile:
    """A deleted file support may still bring back."""

    file_id: UUID
    name: str
    size_bytes: int
    deleted_at: datetime


def in_deletion_window() -> AppError:
    """The account waits for its erasure; only the person's sign-in brings files back."""
    return AppError("account_deletion_scheduled", HTTPStatus.CONFLICT)


class SupportFiles:
    """Support's list and restore of a person's deleted files, each one audited."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[PortDirectory, EventOutbox, QuotaWatch, LeoUse, LeoWatch],
    ) -> None:
        self._transactions = transactions
        self._ports, self._outbox, self._watch, self._leo, self._leo_watch = services

    async def of_person(self, home: Home, user_id: UUID) -> list[HiddenFile]:
        """The person's deleted files, the latest deletion first; the reading is audited."""
        query = (
            select(StorageFileRecord)
            .where(StorageFileRecord.user_id == user_id, StorageFileRecord.deleted_at.is_not(None))
            .order_by(StorageFileRecord.deleted_at.desc())
        )
        async with self._transactions.begin(TenancyScope(home, user_id)) as session:
            if await usage_store.account_hidden(session, user_id):
                raise in_deletion_window()
            rows = list(await session.scalars(query))
            await self._audit(session, AccountRef(user_id, home), OperatorAction.FILES_LISTED)
        return [HiddenFile(r.id, r.name, r.size_bytes, r.deleted_at) for r in rows if r.deleted_at]

    async def restore(self, home: Home, user_id: UUID, file_id: UUID) -> None:
        """Bring a deleted file back into the person's File Manager and quota; audited."""
        limit = await self._watch.limit(home, user_id)
        leo_limit = await self._leo_watch.limit(home, user_id)
        async with self._transactions.begin(TenancyScope(home, user_id)) as session:
            await self._leo.hold(session, user_id)
            await usage_store.lock(session, user_id)
            if await usage_store.account_hidden(session, user_id):
                raise in_deletion_window()
            record = await session.get(StorageFileRecord, file_id, with_for_update=True)
            if record is None or record.user_id != user_id or record.deleted_at is None:
                raise AppError("hidden_file_not_found", HTTPStatus.NOT_FOUND)
            record.deleted_at = None
            await usage_store.add_used(session, user_id, record.size_bytes)
            await self._outbox.add(
                session, FileRestored(file_id=file_id, user_id=user_id, org_id=record.org_id)
            )
            await self._audit(
                session, AccountRef(user_id, home), OperatorAction.FILE_RESTORED, file_id
            )
            await self._leo_back(session, record)
            await self._watch.apply(session, user_id, limit)
            await self._leo_watch.apply(session, user_id, leo_limit)

    async def _leo_back(self, session: AsyncSession, record: StorageFileRecord) -> None:
        """Leo uses the restored file again if its switch or its folder's says so."""
        folder = (
            None
            if record.folder_id is None
            else await session.get(FileFolderRecord, record.folder_id)
        )
        in_leo = frozenset({folder.id}) if folder is not None and folder.leo else frozenset()
        await session.flush()
        shift = LeoShift.of([(unused(record), candidate(record, in_leo))])
        await self._leo.settle(session, record.user_id, shift, None)

    async def _audit(
        self,
        session: AsyncSession,
        target: AccountRef,
        action: OperatorAction,
        subject_id: UUID | None = None,
    ) -> None:
        await self._ports.get(OPERATOR_AUDIT).acted(session, target, action, subject_id)
