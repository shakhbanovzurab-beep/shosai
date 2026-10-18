"""A person's file handed over to a workspace (files plan §3.4 flow 5, step 8a).

One transaction, scoped to the receiving workspace, with the person's locks in their one
order: the Leo lock, the usage row, then the file. Workspaces' `KnowledgeTransfer` makes
the person's shared item the workspace's upload, withdraws the file from every other
workspace and writes the audit row; the file's row then joins the workspace at the level
the item had, leaves its folder and the person's Leo, and its bytes leave the person's
usage (the workspace's own usage comes with FL-D6, step 8b). The object keeps its key.
A repeat answers as the first transfer did.
"""

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.application.file_edits import file_gone
from shosai.features.files.application.leo_use import (
    LeoUse,
    candidate,
    leo_folders,
    own_folders,
    unused,
)
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.domain.leo import LeoShift
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.identity.contracts import Principal
from shosai.features.workspaces.contracts import ACCESS_POLICY, KNOWLEDGE_TRANSFER, Viewer

log = structlog.stdlib.get_logger(__name__)


class FileTransfers:
    """Hands the person's own files over to the workspaces they shared them in."""

    def __init__(
        self, transactions: HomeTransactions, services: tuple[PortDirectory, LeoUse]
    ) -> None:
        self._transactions = transactions
        self._ports, self._leo = services

    async def transfer(self, principal: Principal, file_id: UUID, org_id: UUID) -> None:
        """Make the file the workspace's; 404 for a file not the person's to give."""
        scope = TenancyScope(principal.home, principal.user_id, org_id)
        async with self._transactions.begin(scope) as session:
            await self._leo.hold(session, principal.user_id)
            await usage_store.lock(session, principal.user_id)
            record = await self._mine(session, principal.user_id, file_id)
            if record.org_id == org_id:
                return
            if record.org_id is not None:
                raise file_gone()
            in_leo = leo_folders(list(await session.scalars(own_folders(principal.user_id))))
            before = candidate(record, in_leo)
            port = self._ports.get(KNOWLEDGE_TRANSFER)
            handed = await port.transfer(session, org_id, record.id, principal.user_id)
            record.org_id, record.access, record.folder_id = org_id, handed.level, None
            # Переключатели Leo — личные: у файла пространства их нет.
            record.leo_on, record.leo_held = False, False
            await usage_store.free(session, principal.user_id, record.size_bytes)
            await session.flush()
            shift = LeoShift.of([(before, unused(record))])
            await self._leo.settle(session, principal.user_id, shift, None)
        log.info(
            "Файл передан пространству",
            user_id=str(principal.user_id), org_id=str(org_id), file_id=str(file_id),
        )  # fmt: skip

    async def _mine(self, session: AsyncSession, user_id: UUID, file_id: UUID) -> StorageFileRecord:
        """The person's file they may see, locked; one they already gave is theirs to repeat."""
        query = visible_files(self._ports.get(ACCESS_POLICY), Viewer(user_id)).where(
            StorageFileRecord.id == file_id, StorageFileRecord.user_id == user_id
        )
        record = await session.scalar(query.with_for_update(of=StorageFileRecord))
        if record is None:
            raise file_gone()
        return record
