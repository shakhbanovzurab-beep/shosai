"""A workspace's files follow workspaces' events (files plan step 8a, nfr-16).

A member's departure passes the workspace's files they hold to the owner `member.removed`
names, so no file of a workspace keeps the id of someone who left or was erased; their
personal files stay theirs, and workspaces has already withdrawn the shares. A deleted
workspace's files go for good in the delivery's transaction, with one `files.file.deleted`
each for knowledge; the keys no other row names are recorded, and the upload sweep deletes
their objects in its next pass. A redelivered event finds nothing left to change.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import Row, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.features.files.application.account_data import unnamed
from shosai.features.files.contracts.events import FileDeleted
from shosai.features.files.domain.uploads import UploadState
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.object_deleter import record_deletions
from shosai.features.files.infrastructure.upload_records import UploadRecord
from shosai.features.workspaces.contracts.events import MemberRemoved

FILE: Final = StorageFileRecord
log = structlog.stdlib.get_logger(__name__)

type ErasedRow = Row[UUID, UUID, str, datetime | None]


async def pass_to_successor(session: AsyncSession, removed: MemberRemoved) -> None:
    """The departed member's files of the workspace become its standing owner's."""
    if removed.successor_user_id is None:
        log.warning(
            "У пространства нет владельца: файлы ушедшего участника остались за ним",
            org_id=str(removed.org_id), user_id=str(removed.user_id),
        )  # fmt: skip
        return
    await session.execute(
        update(FILE)
        .where(FILE.org_id == removed.org_id, FILE.user_id == removed.user_id)
        .values(user_id=removed.successor_user_id)
    )


async def erase_workspace_files(session: AsyncSession, outbox: EventOutbox, org_id: UUID) -> None:
    """Remove every file and upload of the deleted workspace; record the orphaned objects."""
    erased = (
        await session.execute(
            delete(FILE)
            .where(FILE.org_id == org_id)
            .returning(FILE.id, FILE.user_id, FILE.object_key, FILE.deleted_at)
        )
    ).all()
    # У готовой, но не забранной загрузки объект уже в бакете; у прочих его нет.
    ready = list(
        await session.scalars(
            delete(UploadRecord)
            .where(UploadRecord.org_id == org_id, UploadRecord.state == UploadState.READY.value)
            .returning(UploadRecord.object_key)
        )
    )
    await session.execute(delete(UploadRecord).where(UploadRecord.org_id == org_id))
    keys = sorted({row.object_key for row in erased} | set(ready))
    await record_deletions(session, await unnamed(session, keys))
    await outbox.add_all(session, _deletions(erased, org_id))
    if erased:
        log.info("Файлы удалённого пространства стёрты", org_id=str(org_id), files=len(erased))


def _deletions(erased: Sequence[ErasedRow], org_id: UUID) -> list[FileDeleted]:
    """One `files.file.deleted` per file still visible until now; hidden ones told already."""
    return [
        FileDeleted(file_id=row.id, user_id=row.user_id, org_id=org_id)
        for row in erased
        if row.deleted_at is None
    ]
