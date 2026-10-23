"""A task's attachments (tasks plan §3.3, §3.13; KG-D3, ADR 0064).

Whoever may read a task attaches to it (TK-D2): their ready `task_attachment` upload, or a
File Manager file they may read, held by files on the file's object. Files keeps the bytes
in the task owner's storage; a workspace's storage opens with files' step 8b (FL-D6), so a
workspace task takes none until then. A task holds at most 50, under its row lock; a
repeated upload is the attachment it already made. Downloads are files' 15-minute links.
A removed attachment clears the cover it was and goes back to files after the commit.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.contracts import UploadNotClaimableError
from shosai.features.files.contracts.held_objects import HELD_OBJECTS, HeldObject, ObjectLink
from shosai.features.files.domain.purposes import UploadPurpose
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, Principal
from shosai.features.tasks.application.attachment_releases import AttachmentReleases
from shosai.features.tasks.application.attachment_views import attachment_of
from shosai.features.tasks.application.scoping import Scoping, locked_task, task_changed
from shosai.features.tasks.application.task_parts import AttachmentView
from shosai.features.tasks.domain.tasks import TaskSource
from shosai.features.tasks.infrastructure.attachment_records import TaskAttachmentRecord
from shosai.features.tasks.infrastructure.task_records import TaskRecord
from shosai.features.workspaces.contracts import Viewer

ATTACHMENTS = TaskAttachmentRecord
ATTACHMENTS_MAX: Final = 50
PURPOSE: Final = UploadPurpose.TASK_ATTACHMENT


@dataclass(frozen=True, slots=True)
class FromUpload:
    """The person's ready upload for the task."""

    upload_id: UUID


@dataclass(frozen=True, slots=True)
class FromFile:
    """A File Manager file the person may read, attached as a copy on its object."""

    file_id: UUID


type AttachmentSource = FromUpload | FromFile


def not_found() -> AppError:
    """No such attachment of the task."""
    return AppError("attachment_not_found", HTTPStatus.NOT_FOUND)


class Attachments:
    """Attaches, links and removes the files of tasks."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._clock = clock
        self._scoping = Scoping(transactions, ports)
        self._releases = AttachmentReleases(transactions, ports)

    async def create(
        self, principal: Principal, task_id: UUID, source: AttachmentSource
    ) -> AttachmentView:
        """The new attachment; the same one for a repeated upload."""
        held = self._ports.get(HELD_OBJECTS)
        scope = await self._scoping.space_of(principal, task_id)
        limit = (
            await held.limit(principal.home, principal.user_id)
            if isinstance(source, FromFile)
            else None
        )
        async with self._transactions.begin(scope) as session:
            task = await locked_task(session, self._ports, principal.user_id, task_id)
            _admit(task)
            if isinstance(source, FromUpload):
                kept = await held.from_upload(session, source.upload_id, PURPOSE)
            else:
                viewer = Viewer(principal.user_id)
                kept = await held.from_file(session, viewer, source.file_id, (PURPOSE, limit))
            record = await self._attach(session, principal.user_id, task, kept)
            names = await self._ports.get(ACCOUNT_PROFILE_READER).names(session, [record.added_by])
            view = attachment_of(record, names)
        if kept.image:
            await held.prepare(scope.home, [kept.id])
        return view

    async def download(
        self, principal: Principal, task_id: UUID, attachment_id: UUID
    ) -> ObjectLink:
        """A 15-minute link to an attachment of a task the person may read."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            await locked_task(session, self._ports, principal.user_id, task_id, lock=False)
            held_id = await session.scalar(
                select(ATTACHMENTS.held_object_id).where(
                    ATTACHMENTS.id == attachment_id, ATTACHMENTS.task_id == task_id
                )
            )
        if held_id is None:
            raise not_found()
        link = (await self._ports.get(HELD_OBJECTS).links(principal.scope(), [held_id])).get(
            held_id
        )
        if link is None:
            raise not_found()
        return link

    async def delete(self, principal: Principal, task_id: UUID, attachment_id: UUID) -> None:
        """Remove the attachment; it stops being the cover, and its object goes back to files."""
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            task = await locked_task(session, self._ports, principal.user_id, task_id)
            gone = await session.scalar(
                delete(ATTACHMENTS)
                .where(ATTACHMENTS.id == attachment_id, ATTACHMENTS.task_id == task_id)
                .returning(ATTACHMENTS.id)
            )
            if gone is None:
                raise not_found()
            await task_changed(session, principal.user_id, task, self._clock())
        await self._releases.owner(scope)

    async def _attach(
        self, session: AsyncSession, viewer: UUID, task: TaskRecord, kept: HeldObject
    ) -> TaskAttachmentRecord:
        """The attachment of the held object: the one a repeat made, or a new one in room."""
        found = await session.scalar(
            select(ATTACHMENTS).where(ATTACHMENTS.held_object_id == kept.id)
        )
        if found is not None:
            if found.task_id != task.id:
                raise UploadNotClaimableError
            return found
        count = await session.scalar(
            select(func.count()).select_from(ATTACHMENTS).where(ATTACHMENTS.task_id == task.id)
        )
        if (count or 0) >= ATTACHMENTS_MAX:
            raise AppError("attachments_full", HTTPStatus.CONFLICT)
        now = self._clock()
        record = TaskAttachmentRecord(
            id=new_id(), task_id=task.id, user_id=task.user_id, org_id=task.org_id,
            held_object_id=kept.id, name=kept.filename, content_type=kept.content_type,
            size_bytes=kept.size_bytes, image=kept.image, added_by=viewer, added_at=now,
        )  # fmt: skip
        session.add(record)
        await task_changed(session, viewer, task, now)
        return record


def _admit(task: TaskRecord) -> None:
    """A Jira task has no files (KG-D8); a workspace's storage is not open yet (FL-D6)."""
    if task.source == TaskSource.JIRA.value:
        raise AppError("jira_unsupported", HTTPStatus.CONFLICT)
    if task.org_id is not None:
        raise AppError("storage_not_included", HTTPStatus.FORBIDDEN)
