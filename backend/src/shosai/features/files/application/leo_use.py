"""Leo's use of a person's files: the person's lock, the knowledge limit and the events.

A change that may start or stop Leo's use of files — a switch on a file or a folder, a
move, a rename, new files, a copy, support's restore — runs the same way. The limit is
read before the transaction. Inside it the person's Leo lock comes first, then the change,
flushed. `settle` then counts the bytes Leo uses now, refuses a change that starts using
files past `knowledge_base_mb` (409 `leo_limit`) and writes one `files.leo_use.changed`
per file whose use changed, all in one statement.
"""

from collections.abc import Sequence
from http import HTTPStatus
from uuid import UUID

import structlog
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.contracts.events import LeoUseChanged
from shosai.features.files.domain.kinds import LEO_MAX_FILE_BYTES
from shosai.features.files.domain.leo import (
    KnowledgeLimitError,
    LeoCandidate,
    LeoShift,
    bytes_in_use,
    knowledge_limit,
)
from shosai.features.files.infrastructure.file_records import FileFolderRecord, StorageFileRecord
from shosai.features.files.infrastructure.leo_lock import hold_leo_lock
from shosai.features.identity.contracts import Principal
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

log = structlog.stdlib.get_logger(__name__)


def leo_limit(limit: int | None) -> AppError:
    """Leo would use more than the plan's knowledge limit."""
    return AppError("leo_limit", HTTPStatus.CONFLICT, params={"limit_bytes": limit or 0})


def leo_unreadable() -> AppError:
    """The file's own switch is for files Leo can read: nine types up to 50 MiB."""
    return AppError("leo_unreadable", HTTPStatus.CONFLICT)


def leo_not_used() -> AppError:
    """Leo does not use the file, so there is nothing to read again."""
    return AppError("leo_not_used", HTTPStatus.CONFLICT)


def own_folders(user_id: UUID) -> Select[FileFolderRecord]:
    """The person's folders by name."""
    return (
        select(FileFolderRecord)
        .where(FileFolderRecord.user_id == user_id)
        .order_by(FileFolderRecord.name, FileFolderRecord.id)
    )


def leo_folders(folders: Sequence[FileFolderRecord]) -> frozenset[UUID]:
    """The folders whose files Leo uses."""
    return frozenset(folder.id for folder in folders if folder.leo)


def candidate(record: StorageFileRecord, leo_folder_ids: frozenset[UUID]) -> LeoCandidate:
    """The file as Leo's use sees it now."""
    folder = record.folder_id is not None and record.folder_id in leo_folder_ids
    return LeoCandidate(record.id, record.name, record.size_bytes, record.leo_on, folder)


def unused(record: StorageFileRecord) -> LeoCandidate:
    """A file before it existed for Leo: a new file or a hidden one."""
    return LeoCandidate(record.id, record.name, record.size_bytes, own=False, folder=False)


class LeoUse:
    """The lock, the limit and the announcements of changes of Leo's use."""

    def __init__(self, ports: PortDirectory, outbox: EventOutbox) -> None:
        self._ports, self._outbox = ports, outbox

    async def limit(self, principal: Principal) -> int | None:
        """The plan's knowledge limit in bytes, read before the transaction; 503 unread."""
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(principal.home, principal.user_id)
        return knowledge_limit(snapshot.limits.knowledge_base_mb)

    async def hold(self, session: AsyncSession, user_id: UUID) -> None:
        """Take the person's Leo lock: the first statement of a change of Leo's use."""
        await hold_leo_lock(session, user_id)

    async def settle(
        self, session: AsyncSession, user_id: UUID, shift: LeoShift, limit: int | None
    ) -> None:
        """Check the flushed change against the limit and announce each file it changed."""
        if shift.empty:
            return
        if shift.started:
            in_use = bytes_in_use(await self._in_use(session, user_id))
            try:
                shift.check(in_use, limit)
            except KnowledgeLimitError as error:
                log.info("Лимит знаний Leo не пропустил изменение", user_id=str(user_id))
                raise leo_limit(limit) from error
        events = [
            *(
                LeoUseChanged(file_id=file_id, user_id=user_id, used=True)
                for file_id in shift.started
            ),
            *(
                LeoUseChanged(file_id=file_id, user_id=user_id, used=False)
                for file_id in sorted(shift.stopped)
            ),
        ]
        await self._outbox.add_all(session, events)
        log.info(
            "Использование файлов Leo изменилось", user_id=str(user_id),
            started=len(shift.started), stopped=len(shift.stopped),
        )  # fmt: skip

    async def _in_use(self, session: AsyncSession, user_id: UUID) -> list[LeoCandidate]:
        """The person's own visible files Leo may use: a switch on and at most 50 MiB."""
        in_leo_folder = StorageFileRecord.folder_id.in_(
            select(FileFolderRecord.id).where(
                FileFolderRecord.user_id == user_id, FileFolderRecord.leo
            )
        )
        query = (
            visible_files(self._ports.get(ACCESS_POLICY), Viewer(user_id))
            .with_only_columns(
                StorageFileRecord.id,
                StorageFileRecord.name,
                StorageFileRecord.size_bytes,
                StorageFileRecord.leo_on,
                in_leo_folder,
            )
            .where(
                StorageFileRecord.user_id == user_id,
                StorageFileRecord.org_id.is_(None),
                StorageFileRecord.size_bytes <= LEO_MAX_FILE_BYTES,
                or_(StorageFileRecord.leo_on, in_leo_folder),
            )
        )
        rows = (await session.execute(query)).all()
        return [LeoCandidate(row[0], row[1], row[2], row[3], bool(row[4])) for row in rows]
