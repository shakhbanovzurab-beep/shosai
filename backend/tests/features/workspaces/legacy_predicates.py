"""The access policy's predicates as they were before `= ANY(...)` (workspaces plan §3.5).

A frozen copy of the readable and manageable predicates whose pre-filters were
`IN (subquery)`: PostgreSQL could not use an index for them under the policy's `OR`, so a
person-wide list read the whole table. The predicate-form test holds the current
predicates to this copy on random worlds; nothing else may use it.
"""

from typing import cast
from uuid import UUID

from sqlalchemy import ColumnElement, Select, Table, and_, exists, false, or_, select, true

from shosai.core.access.shareable import ShareableResource
from shosai.features.workspaces.domain.memberships import MembershipState
from shosai.features.workspaces.infrastructure.organization_records import (
    Membership,
    Organization,
)
from shosai.features.workspaces.infrastructure.policy_predicates import (
    ACTIVE_WORKSPACE,
    MANAGERS,
    _member_of,
    level_admits,
)
from shosai.features.workspaces.infrastructure.share_records import SHARE_RECORDS, ShareRecords

MEMBERSHIPS = cast("Table", Membership.__table__)
WORKSPACES = cast("Table", Organization.__table__)


def _member_orgs(user_id: UUID, within: UUID | None) -> Select[tuple[UUID]]:
    member, workspace = MEMBERSHIPS.alias(), WORKSPACES.alias()
    query = (
        select(member.c.org_id)
        .join(workspace, workspace.c.id == member.c.org_id)
        .where(
            member.c.user_id == user_id,
            member.c.state == MembershipState.ACTIVE,
            workspace.c.state == ACTIVE_WORKSPACE,
        )
    )
    return query.where(member.c.org_id == within) if within is not None else query


def workspace_rows(
    resource: ShareableResource, user_id: UUID, within: UUID | None, *, manage: bool
) -> ColumnElement[bool]:
    table = resource.table
    row_id, owner, org, level = (table.c[name] for name in resource.column_names())
    member, joined, conditions = _member_of(org, user_id)
    admits = level_admits(level, org, (resource.kind, row_id), member)
    if manage:
        admits = and_(member.c.role.in_(MANAGERS), admits)
    in_view = (
        exists()
        .select_from(joined)
        .where(*conditions, or_(owner == user_id, admits))
        .correlate_except(joined)
    )
    return and_(org.in_(_member_orgs(user_id, within)), in_view)


def personal_rows(
    resource: ShareableResource, user_id: UUID, within: UUID | None, *, manage: bool
) -> ColumnElement[bool]:
    table = resource.table
    owner, org = table.c[resource.owner], table.c[resource.org]
    own = owner == user_id if within is None or manage else false()
    records = SHARE_RECORDS.get(resource.kind)
    shared = _shared(resource, records, user_id, within, manage=manage) if records else false()
    return and_(org.is_(None), or_(own, shared))


def _shared(
    resource: ShareableResource,
    records: ShareRecords,
    user_id: UUID,
    within: UUID | None,
    *,
    manage: bool,
) -> ColumnElement[bool]:
    table = resource.table
    row_id, owner = table.c[resource.id], table.c[resource.owner]
    share = records.table.alias()
    org = share.c[records.org]
    member, joined, conditions = _member_of(org, user_id)
    sharer = MEMBERSHIPS.alias()
    admits = level_admits(
        share.c[records.access], org, (records.grant_kind, share.c[records.grant_key]), member
    )
    if manage:
        admits = and_(member.c.role.in_(MANAGERS), admits)
    filters = [
        share.c[records.resource] == row_id,
        sharer.c.id == share.c[records.sharer],
        sharer.c.state == MembershipState.ACTIVE,
        sharer.c.user_id == owner,
    ]
    if records.only is not None:
        column, value = records.only
        filters.append(share.c[column] == value)
    if within is not None:
        filters.append(org == within)
    sources = share.join(joined, true()).join(sharer, true())
    exact = (
        exists()
        .select_from(sources)
        .where(*filters, *conditions, or_(owner == user_id, admits))
        .correlate_except(sources)
    )
    candidates = records.table.alias()
    shared_in_mine = select(candidates.c[records.resource]).where(
        candidates.c[records.org].in_(_member_orgs(user_id, within))
    )
    return and_(row_id.in_(shared_in_mine), exact)


def legacy_readable(
    resource: ShareableResource, user_id: UUID, within: UUID | None
) -> ColumnElement[bool]:
    """The former readable predicate."""
    return or_(
        workspace_rows(resource, user_id, within, manage=False),
        personal_rows(resource, user_id, within, manage=False),
    )


def legacy_manageable(
    resource: ShareableResource, user_id: UUID, within: UUID | None
) -> ColumnElement[bool]:
    """The former manageable predicate."""
    return or_(
        workspace_rows(resource, user_id, within, manage=True),
        personal_rows(resource, user_id, within, manage=True),
    )
