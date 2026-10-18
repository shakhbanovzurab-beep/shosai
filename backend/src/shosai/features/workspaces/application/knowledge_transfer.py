"""Handing a member's shared file over to the workspace: the port files' transfer calls (§3.2).

Everything happens in the caller's transaction, scoped to the receiving workspace. The
member's personal item of the file there becomes the workspace's upload and keeps its id
and level; its grants move under the file, because a workspace's file is read through its
own row and grants (§7). The file's items in every other workspace go with their grants,
one `knowledge_item.removed` each, and one `file_transferred` audit row is written.

The file's items are locked first, in one order, so two transfers of one file into two
workspaces never deadlock: the second waits, finds its item gone and is refused like a
file never shared there.
"""

from collections.abc import Sequence
from http import HTTPStatus
from typing import Final
from uuid import UUID

from sqlalchemy import Row, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import transaction_info
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.features.workspaces.application.acting import acting_member
from shosai.features.workspaces.contracts import (
    AccessLevel,
    AuditAction,
    AuditEntry,
    AuditLog,
    TransferredFile,
)
from shosai.features.workspaces.contracts.events import KnowledgeItemRemoved
from shosai.features.workspaces.domain.memberships import MembershipState
from shosai.features.workspaces.infrastructure.access_records import (
    ResourceGrant,
    WorkspaceKnowledgeItem,
)
from shosai.features.workspaces.infrastructure.organization_records import Membership
from shosai.features.workspaces.infrastructure.share_records import (
    FILE_KIND,
    KNOWLEDGE_ITEM_KIND,
)

PERSONAL: Final = "personal"
UPLOAD: Final = "upload"
ITEM: Final = WorkspaceKnowledgeItem

type ItemRow = Row[UUID, UUID, str, str, UUID | None]


class TransferScopeMismatchError(ValueError):
    """A transfer ran in a transaction scoped to another workspace than the receiving one."""


class WorkspaceKnowledgeTransfer:
    """Makes a member's shared file the workspace's own and withdraws it everywhere else."""

    def __init__(self, outbox: EventOutbox, audit: AuditLog) -> None:
        self._outbox = outbox
        self._audit = audit

    async def transfer(
        self, session: AsyncSession, org_id: UUID, file_id: UUID, actor_id: UUID
    ) -> TransferredFile:
        """Make the actor's personal item of the file the workspace's upload."""
        if transaction_info(session).scope.org_id != org_id:
            message = "передача файла идёт в транзакции принимающего пространства"
            raise TransferScopeMismatchError(message)
        acting = await acting_member(session, org_id, actor_id)
        items = await _locked_items(session, file_id, actor_id)
        here = next((item for item in items if item.org_id == org_id), None)
        if here is None or here.added_by_membership_id != acting.actor.membership_id:
            raise AppError("share_first", HTTPStatus.CONFLICT)
        transferred = TransferredFile(here.id, AccessLevel(here.access))
        # Повтор: файл уже отдан этим участником, отвечаем тем же элементом.
        if here.source_kind == UPLOAD:
            return transferred
        await _adopt(session, org_id, here.id, file_id)
        await self._withdraw(session, [item for item in items if item.org_id != org_id])
        entry = AuditEntry(
            org_id, AuditAction.FILE_TRANSFERRED, acting.actor.membership_id, FILE_KIND, file_id
        )
        await self._audit.record(session, entry)
        return transferred

    async def _withdraw(self, session: AsyncSession, items: Sequence[ItemRow]) -> None:
        """The file's personal items in other workspaces go, with their grants and events."""
        withdrawn = [item for item in items if item.source_kind == PERSONAL]
        if not withdrawn:
            return
        ids = [item.id for item in withdrawn]
        await session.execute(
            delete(ResourceGrant).where(
                ResourceGrant.resource_kind == KNOWLEDGE_ITEM_KIND,
                ResourceGrant.resource_id.in_(ids),
            )
        )
        await session.execute(delete(ITEM).where(ITEM.id.in_(ids)))
        events = [KnowledgeItemRemoved(org_id=item.org_id, item_id=item.id) for item in withdrawn]
        await self._outbox.add_all(session, events)


async def _locked_items(session: AsyncSession, file_id: UUID, actor_id: UUID) -> list[ItemRow]:
    """The file's items in the actor's workspaces, locked in id order.

    A personal file is shared only by its owner, and a membership that ends takes its
    shared files with it, so the actor's active workspaces hold every item of the file.
    """
    workspaces = select(Membership.org_id).where(
        Membership.user_id == actor_id, Membership.state == MembershipState.ACTIVE
    )
    query = (
        select(ITEM.id, ITEM.org_id, ITEM.source_kind, ITEM.access, ITEM.added_by_membership_id)
        .where(ITEM.file_id == file_id, ITEM.org_id.in_(workspaces))
        .order_by(ITEM.id)
        .with_for_update(of=ITEM)
    )
    return list((await session.execute(query)).all())


async def _adopt(session: AsyncSession, org_id: UUID, item_id: UUID, file_id: UUID) -> None:
    """The item becomes the workspace's upload; its grants now name the file."""
    await session.execute(update(ITEM).where(ITEM.id == item_id).values(source_kind=UPLOAD))
    await session.execute(
        update(ResourceGrant)
        .where(
            ResourceGrant.org_id == org_id,
            ResourceGrant.resource_kind == KNOWLEDGE_ITEM_KIND,
            ResourceGrant.resource_id == item_id,
        )
        .values(resource_kind=FILE_KIND, resource_id=file_id)
    )
