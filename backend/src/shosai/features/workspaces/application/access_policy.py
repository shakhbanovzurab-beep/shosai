"""The one access policy every slice reads and shares its rows through (§7, inv-14).

`readable` and `manageable` return the predicate a slice puts into its own query, so the
check runs with the read and nothing is cached. `filter_readable` re-checks a batch of
ids — search hits, Leo's sources — in one query. `set_access` is the only way to change a
workspace row's level and grants: in the caller's transaction, with its audit row and
event, and only by someone who may manage the row.
"""

from collections.abc import Collection
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.access.shareable import ShareableResource
from shosai.core.db.transactions import transaction_info
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.features.workspaces.contracts import (
    AccessChange,
    AccessLevel,
    AuditAction,
    AuditEntry,
    AuditLog,
    GranteeKind,
    Viewer,
)
from shosai.features.workspaces.contracts.events import AccessChanged
from shosai.features.workspaces.domain.memberships import MembershipState
from shosai.features.workspaces.infrastructure.access_records import ResourceGrant
from shosai.features.workspaces.infrastructure.organization_records import Membership, Team
from shosai.features.workspaces.infrastructure.policy_predicates import (
    personal_rows,
    workspace_rows,
)


class AccessScopeMismatchError(ValueError):
    """`set_access` ran in a transaction scoped to another workspace than the change's."""


class WorkspaceAccessPolicy:
    """Builds the predicates of every read and applies every access change."""

    def __init__(self, outbox: EventOutbox, audit: AuditLog) -> None:
        self._outbox = outbox
        self._audit = audit

    def readable(self, resource: ShareableResource, viewer: Viewer) -> ColumnElement[bool]:
        """The predicate that admits exactly the rows the viewer may read."""
        return or_(
            workspace_rows(resource, viewer.user_id, viewer.within, manage=False),
            personal_rows(resource, viewer.user_id, viewer.within, manage=False),
        )

    def manageable(self, resource: ShareableResource, viewer: Viewer) -> ColumnElement[bool]:
        """The predicate that admits exactly the rows whose access the viewer may change."""
        return or_(
            workspace_rows(resource, viewer.user_id, viewer.within, manage=True),
            personal_rows(resource, viewer.user_id, viewer.within, manage=True),
        )

    async def filter_readable(
        self,
        session: AsyncSession,
        resource: ShareableResource,
        ids: Collection[UUID],
        viewer: Viewer,
    ) -> frozenset[UUID]:
        """The ids the viewer may read now, in one query."""
        if not ids:
            return frozenset()
        row_id = resource.table.c[resource.id]
        query = select(row_id).where(row_id.in_(list(ids)), self.readable(resource, viewer))
        return frozenset(await session.scalars(query))

    async def set_access(self, session: AsyncSession, change: AccessChange) -> None:
        """Write the level, the grants, the audit row and the event in the caller's transaction."""
        if transaction_info(session).scope.org_id != change.org_id:
            message = "смена доступа идёт в транзакции своего пространства"
            raise AccessScopeMismatchError(message)
        _check_grantees(change)
        table, resource = change.resource.table, change.resource
        row_id, org = table.c[resource.id], table.c[resource.org]
        target = select(row_id).where(row_id == change.resource_id, org == change.org_id)
        if change.actor is not None:
            target = target.where(self.manageable(resource, change.actor))
        if await session.scalar(target.with_for_update()) is None:
            raise AppError("resource_not_found", HTTPStatus.NOT_FOUND)
        await _require_grantees_of(session, change)
        await session.execute(
            update(table)
            .where(row_id == change.resource_id)
            .values({resource.access: change.level})
        )
        await _replace_grants(session, change)
        actor = await _actor_membership(session, change)
        entry = AuditEntry(
            change.org_id,
            AuditAction.ACCESS_CHANGED,
            actor,
            resource.kind,
            change.resource_id,
            change.level,
        )
        await self._audit.record(session, entry)
        event = AccessChanged(
            org_id=change.org_id,
            resource_kind=resource.kind,
            resource_id=change.resource_id,
            level=change.level,
        )
        await self._outbox.add(session, event)


def _check_grantees(change: AccessChange) -> None:
    """`selected` names at least one grantee; the other levels name none."""
    named = bool(change.grantees)
    if (change.level is AccessLevel.SELECTED) != named:
        raise AppError("grantees_invalid", HTTPStatus.UNPROCESSABLE_ENTITY)


async def _require_grantees_of(session: AsyncSession, change: AccessChange) -> None:
    """Every member grantee is an active member and every team a team of the workspace."""
    members = {g.id for g in change.grantees if g.kind is GranteeKind.MEMBER}
    teams = {g.id for g in change.grantees if g.kind is GranteeKind.TEAM}
    found_members = await session.scalar(
        select(func.count()).where(
            Membership.id.in_(members),
            Membership.org_id == change.org_id,
            Membership.state == MembershipState.ACTIVE,
        )
    ) if members else 0  # fmt: skip
    found_teams = await session.scalar(
        select(func.count()).where(Team.id.in_(teams), Team.org_id == change.org_id)
    ) if teams else 0  # fmt: skip
    if found_members != len(members) or found_teams != len(teams):
        raise AppError("grantees_invalid", HTTPStatus.UNPROCESSABLE_ENTITY)


async def _replace_grants(session: AsyncSession, change: AccessChange) -> None:
    kind = change.resource.kind
    await session.execute(
        delete(ResourceGrant).where(
            ResourceGrant.org_id == change.org_id,
            ResourceGrant.resource_kind == kind,
            ResourceGrant.resource_id == change.resource_id,
        )
    )
    if change.grantees:
        rows = [
            {
                "org_id": change.org_id,
                "resource_kind": kind,
                "resource_id": change.resource_id,
                "grantee_kind": grantee.kind.value,
                "grantee_id": grantee.id,
            }
            for grantee in sorted(change.grantees)
        ]
        await session.execute(insert(ResourceGrant), rows)


async def _actor_membership(session: AsyncSession, change: AccessChange) -> UUID | None:
    """The acting member's membership for the audit row; None for the platform's admin."""
    if change.actor is None:
        return None
    return await session.scalar(
        select(Membership.id).where(
            Membership.org_id == change.org_id, Membership.user_id == change.actor.user_id
        )
    )
