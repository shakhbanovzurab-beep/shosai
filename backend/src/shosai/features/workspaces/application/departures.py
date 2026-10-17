"""Ending a membership: removal by an admin, leaving, or the account's erasure (§3.6 flow 3).

The membership becomes `removed` and the workspace's access ends at the next statement,
because every reading query checks it. In the same transaction the member's grants,
team places, leads and shared items go, an audit row is written and `member.removed`
names the owner who inherits what the person created in the workspace (nfr-16).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.features.workspaces.contracts import AuditAction, AuditEntry, AuditLog
from shosai.features.workspaces.contracts.events import MemberRemoved
from shosai.features.workspaces.domain.memberships import STANDING, MembershipState, RemovalReason
from shosai.features.workspaces.domain.roles import WorkspaceRole
from shosai.features.workspaces.infrastructure.member_withdrawal import withdraw_member
from shosai.features.workspaces.infrastructure.organization_records import Membership


@dataclass(frozen=True, slots=True)
class Ending:
    """One membership to end, why, and who ends it (None: the platform or an erasure)."""

    org_id: UUID
    membership_id: UUID
    user_id: UUID
    reason: RemovalReason
    actor_membership_id: UUID | None


async def end_membership(
    session: AsyncSession, ending: Ending, outbox: EventOutbox, audit: AuditLog
) -> None:
    """End the membership in the caller's transaction; the workspace keeps an owner."""
    # Должность — данные человека: стирание их убирает, удаление из пространства — нет.
    erased = ending.reason is RemovalReason.ACCOUNT_ERASED
    values: dict[str, object] = {
        "state": MembershipState.REMOVED,
        "removed_at": datetime.now(UTC),
        "removal_reason": ending.reason,
    }
    if erased:
        values["title"] = None
    await session.execute(
        update(Membership).where(Membership.id == ending.membership_id).values(values)
    )
    await withdraw_member(session, ending.org_id, ending.membership_id)
    action = (
        AuditAction.MEMBER_LEFT
        if ending.reason is RemovalReason.LEFT
        else AuditAction.MEMBER_REMOVED
    )
    entry = AuditEntry(
        ending.org_id,
        action,
        ending.actor_membership_id,
        "membership",
        ending.membership_id,
        ending.reason,
    )
    await audit.record(session, entry)
    event = MemberRemoved(
        org_id=ending.org_id,
        user_id=ending.user_id,
        membership_id=ending.membership_id,
        reason=ending.reason,
        successor_user_id=await standing_owner(session, ending.org_id),
    )
    await outbox.add(session, event)


async def standing_owner(session: AsyncSession, org_id: UUID) -> UUID | None:
    """The longest-standing owner of the workspace: who inherits a departed member's work."""
    return await session.scalar(
        select(Membership.user_id)
        .where(
            Membership.org_id == org_id,
            Membership.role == WorkspaceRole.OWNER,
            Membership.state.in_([state.value for state in STANDING]),
        )
        .order_by(Membership.joined_at)
        .limit(1)
    )
