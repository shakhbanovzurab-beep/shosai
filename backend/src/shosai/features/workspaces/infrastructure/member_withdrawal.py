"""What a membership leaves behind when it ends, cleared in the transaction that ends it (§3.6).

The member's grants and team places go, teams and projects they led lose their lead, and
the recordings and personal files they shared are withdrawn with their grants. Uploads
and connected sources stay with the workspace. Every statement is bounded by the
workspace, which row-level security already enforces through the transaction's scope.
"""

from uuid import UUID

from sqlalchemy import and_, delete, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.workspaces.domain.access import GranteeKind
from shosai.features.workspaces.infrastructure.access_records import (
    ResourceGrant,
    WorkspaceKnowledgeItem,
    WorkspaceMeetingShare,
)
from shosai.features.workspaces.infrastructure.organization_records import (
    Project,
    Team,
    TeamMember,
)

# Виды ресурсов, под которыми записи шаринга хранят свои гранты.
MEETING_KIND = "meeting"
KNOWLEDGE_ITEM_KIND = "knowledge_item"


async def withdraw_member(session: AsyncSession, org_id: UUID, membership_id: UUID) -> None:
    """Clear what an ended membership holds in its workspace."""
    shares = await session.scalars(
        delete(WorkspaceMeetingShare)
        .where(
            WorkspaceMeetingShare.org_id == org_id,
            WorkspaceMeetingShare.shared_by_membership_id == membership_id,
        )
        .returning(WorkspaceMeetingShare.session_id)
    )
    items = await session.scalars(
        delete(WorkspaceKnowledgeItem)
        .where(
            WorkspaceKnowledgeItem.org_id == org_id,
            WorkspaceKnowledgeItem.added_by_membership_id == membership_id,
            WorkspaceKnowledgeItem.source_kind == "personal",
        )
        .returning(WorkspaceKnowledgeItem.id)
    )
    withdrawn = [(MEETING_KIND, share) for share in shares] + [
        (KNOWLEDGE_ITEM_KIND, item) for item in items
    ]
    member_grant = and_(
        ResourceGrant.grantee_kind == GranteeKind.MEMBER, ResourceGrant.grantee_id == membership_id
    )
    resource_grants = [
        and_(ResourceGrant.resource_kind == kind, ResourceGrant.resource_id == resource)
        for kind, resource in withdrawn
    ]
    await session.execute(
        delete(ResourceGrant).where(
            ResourceGrant.org_id == org_id, or_(member_grant, *resource_grants)
        )
    )
    await session.execute(
        delete(TeamMember).where(
            TeamMember.org_id == org_id, TeamMember.membership_id == membership_id
        )
    )
    for led in (Team, Project):
        await session.execute(
            update(led)
            .where(led.org_id == org_id, led.lead_membership_id == membership_id)
            .values(lead_membership_id=None)
        )
