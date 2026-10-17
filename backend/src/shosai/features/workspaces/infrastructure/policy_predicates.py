"""The SQL of the access policy: who may read, or manage, a row of a shareable resource (§7).

A row of a workspace opens to its active members at the row's level in an active
workspace; its owner reads it while still a member. A personal row opens to its owner,
and to the members of each active workspace it is shared into, at the share's level,
while the member who shared it is still an active member there. Every check is an
`EXISTS` correlated with the resource's own row, so it runs inside the slice's query.
Correlation is explicit at every level (`correlate_except`): SQLAlchemy correlates only
with the immediately enclosing query, and a nested check would otherwise read every
row. Aliases are anonymous, so the checks nest without clashing. Unknown levels admit
nobody.
"""

from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    FromClause,
    Select,
    Table,
    and_,
    exists,
    false,
    or_,
    select,
    true,
)

from shosai.core.access.shareable import ShareableResource
from shosai.features.workspaces.domain.access import AccessLevel, GranteeKind
from shosai.features.workspaces.domain.memberships import MembershipState
from shosai.features.workspaces.domain.roles import MANAGING_ROLES, WorkspaceRole
from shosai.features.workspaces.infrastructure.access_records import ResourceGrant
from shosai.features.workspaces.infrastructure.organization_records import (
    Membership,
    Organization,
    TeamMember,
)
from shosai.features.workspaces.infrastructure.share_records import SHARE_RECORDS, ShareRecords

ACTIVE_WORKSPACE = "active"
MANAGERS = tuple(role.value for role in MANAGING_ROLES)


def _table(model: type[Membership | Organization | ResourceGrant | TeamMember]) -> Table:
    table = model.__table__
    if not isinstance(table, Table):
        message = f"у модели {model.__name__} нет таблицы"
        raise TypeError(message)
    return table


def level_admits(
    level: ColumnElement[str],
    org: ColumnElement[UUID],
    grant: tuple[str, ColumnElement[UUID]],
    member: FromClause,
) -> ColumnElement[bool]:
    """Whether a level and its grants admit the active membership `member` (an alias)."""
    grant_kind, grant_key = grant
    grants = _table(ResourceGrant).alias()
    places = _table(TeamMember).alias()
    in_team = (
        exists()
        .where(places.c.team_id == grants.c.grantee_id, places.c.membership_id == member.c.id)
        .correlate_except(places)
    )
    granted = (
        exists()
        .where(
            grants.c.org_id == org,
            grants.c.resource_kind == grant_kind,
            grants.c.resource_id == grant_key,
            or_(
                and_(
                    grants.c.grantee_kind == GranteeKind.MEMBER, grants.c.grantee_id == member.c.id
                ),
                and_(grants.c.grantee_kind == GranteeKind.TEAM, in_team),
            ),
        )
        .correlate_except(grants)
    )
    return or_(
        and_(level == AccessLevel.ORGANIZATION, member.c.role != WorkspaceRole.GUEST),
        and_(level == AccessLevel.SELECTED, granted),
    )


def _member_of(
    org: ColumnElement[UUID], user_id: UUID
) -> tuple[FromClause, FromClause, list[ColumnElement[bool]]]:
    """The viewer's membership alias, joined with its workspace, and the active conditions."""
    member = _table(Membership).alias()
    workspace = _table(Organization).alias()
    conditions = [
        member.c.org_id == org,
        member.c.user_id == user_id,
        member.c.state == MembershipState.ACTIVE,
        workspace.c.id == org,
        workspace.c.state == ACTIVE_WORKSPACE,
    ]
    return member, member.join(workspace, workspace.c.id == member.c.org_id), conditions


def _member_orgs(user_id: UUID, within: UUID | None) -> Select[tuple[UUID]]:
    """The active workspaces the viewer is an active member of: an uncorrelated pre-filter.

    PostgreSQL computes it once per statement and can reach the resource's rows through its
    company index; the correlated checks then decide each row exactly.
    """
    member = _table(Membership).alias()
    workspace = _table(Organization).alias()
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
    """Rows of a workspace the viewer may read, or manage when `manage` is set."""
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
    """Personal rows the viewer owns, or that are shared to them through a workspace."""
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
    sharer = _table(Membership).alias()
    admits = level_admits(
        share.c[records.access], org, (records.grant_kind, share.c[records.grant_key]), member
    )
    if manage:
        admits = and_(member.c.role.in_(MANAGERS), admits)
    filters = [
        share.c[records.resource] == row_id,
        sharer.c.id == share.c[records.sharer],
        sharer.c.state == MembershipState.ACTIVE,
        # Делиться ресурсом может только его владелец.
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
    # Предфильтр без корреляции: ресурсы, поделённые в пространства читателя, — по ключу записи.
    candidates = records.table.alias()
    shared_in_mine = select(candidates.c[records.resource]).where(
        candidates.c[records.org].in_(_member_orgs(user_id, within))
    )
    return and_(row_id.in_(shared_in_mine), exact)
