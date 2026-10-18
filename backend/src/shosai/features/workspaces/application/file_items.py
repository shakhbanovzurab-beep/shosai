"""A file's knowledge items across its owner's workspaces: found, locked and withdrawn (§3.6).

files' transfer and a file's deletion take the file out of the workspaces it was shared
in. A personal file is shared only by its owner, and a membership that ends takes its
shared files with it, so the owner's active workspaces hold every item of the file. The
items are locked in id order, so two changes of one file never deadlock. A withdrawn item
goes with its grants, one `knowledge_item.removed` each.
"""

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import Row, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.features.workspaces.contracts.events import KnowledgeItemRemoved
from shosai.features.workspaces.domain.memberships import MembershipState
from shosai.features.workspaces.infrastructure.access_records import (
    ResourceGrant,
    WorkspaceKnowledgeItem,
)
from shosai.features.workspaces.infrastructure.organization_records import Membership
from shosai.features.workspaces.infrastructure.share_records import KNOWLEDGE_ITEM_KIND

PERSONAL: Final = "personal"
UPLOAD: Final = "upload"
ITEM: Final = WorkspaceKnowledgeItem

type ItemRow = Row[UUID, UUID, str, str, UUID | None]


async def locked_items(session: AsyncSession, file_id: UUID, owner_id: UUID) -> list[ItemRow]:
    """The file's items in its owner's active workspaces, locked in id order."""
    workspaces = select(Membership.org_id).where(
        Membership.user_id == owner_id, Membership.state == MembershipState.ACTIVE
    )
    query = (
        select(ITEM.id, ITEM.org_id, ITEM.source_kind, ITEM.access, ITEM.added_by_membership_id)
        .where(ITEM.file_id == file_id, ITEM.org_id.in_(workspaces))
        .order_by(ITEM.id)
        .with_for_update(of=ITEM)
    )
    return list((await session.execute(query)).all())


async def withdraw_items(
    session: AsyncSession, outbox: EventOutbox, items: Sequence[ItemRow]
) -> None:
    """The personal items among `items` go, with their grants and events."""
    withdrawn = [item for item in items if item.source_kind == PERSONAL]
    if not withdrawn:
        return
    ids = [item.id for item in withdrawn]
    await session.execute(
        delete(ResourceGrant).where(
            ResourceGrant.resource_kind == KNOWLEDGE_ITEM_KIND, ResourceGrant.resource_id.in_(ids)
        )
    )
    await session.execute(delete(ITEM).where(ITEM.id.in_(ids)))
    events = [KnowledgeItemRemoved(org_id=item.org_id, item_id=item.id) for item in withdrawn]
    await outbox.add_all(session, events)
