"""The SQL of the access policy: who may read, or manage, a row of a shareable resource (§7).

A row of a workspace opens to its active members at the row's level in an active
workspace; its owner reads it while still a member. A personal row opens to its owner,
and to the members of each active workspace it is shared into, at the share's level,
while the member who shared it is still an active member there. Every check is an
`EXISTS` correlated with the resource's own row, so it runs inside the slice's query; its
pre-filters are arrays compared with `= ANY(...)`, so indexes serve them under the `OR`.
Correlation is explicit at every level (`correlate_except`): SQLAlchemy correlates only
with the immediately enclosing query, and a nested check would otherwise read every
row. Aliases are anonymous, so the checks nest without clashing. Unknown levels admit
nobody.
"""

from collections.abc import Collection
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    ColumnElement,
    FromClause,
    Select,
    Table,
    Uuid,
    and_,
    any_,
    cast,
    exists,
    false,
    func,
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


def _member_orgs(user_id: UUID, within: UUID | None) -> ColumnElement[Any]:
    """The active workspaces the viewer is an active member of, as one array: a pre-filter.

    It is uncorrelated, so PostgreSQL computes it once per statement, and an array compared
    with `= ANY(...)` is an index condition even under the policy's `OR`: the planner can
    combine the company index with the owner's and the id's (a bitmap OR), where `IN
    (subquery)` there was only a filter, and a person-wide list read the whole table. The
    correlated checks then decide each row exactly. An empty array admits no row.
    """
    member = _table(Membership).alias()
    workspace = _table(Organization).alias()
    query = (
        select(func.array_agg(member.c.org_id))
        .join(workspace, workspace.c.id == member.c.org_id)
        .where(
            member.c.user_id == user_id,
            member.c.state == MembershipState.ACTIVE,
            workspace.c.state == ACTIVE_WORKSPACE,
        )
    )
    narrowed = query.where(member.c.org_id == within) if within is not None else query
    return any_(as_array(narrowed))


def as_array(query: Select[Any]) -> ColumnElement[Any]:
    """A one-column `array_agg` query as an array value: `= ANY (CAST((SELECT …) AS uuid[]))`.

    Without the cast SQLAlchemy writes `= ANY (SELECT …)`, which compares the value with each
    row of the subquery, here a single row holding the whole array.
    """
    return cast(query.scalar_subquery(), ARRAY(Uuid))


def workspace_rows(
    resource: ShareableResource,
    user_id: UUID,
    within: UUID | None,
    *,
    manage: bool,
    through_parent: ColumnElement[bool] | None = None,
) -> ColumnElement[bool]:
    """Rows of a workspace the viewer may read, or manage when `manage` is set.

    Reading also admits the active member the row's reader column names, and whoever may
    read its parent row (`through_parent`, built by the policy); neither manages access.
    """
    table = resource.table
    row_id, owner, org, level = (table.c[name] for name in resource.column_names())
    member, joined, conditions = _member_of(org, user_id)
    admits = level_admits(level, org, (resource.kind, row_id), member)
    widened: list[ColumnElement[bool]] = []
    if manage:
        admits = and_(member.c.role.in_(MANAGERS), admits)
    else:
        if resource.reader is not None:
            widened.append(table.c[resource.reader] == user_id)
        if through_parent is not None:
            widened.append(through_parent)
    in_view = (
        exists()
        .select_from(joined)
        .where(*conditions, or_(owner == user_id, admits, *widened))
        .correlate_except(joined)
    )
    return and_(org == _member_orgs(user_id, within), in_view)


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
    # Предфильтр без корреляции, в двух формах одного списка: хэшированный IN первым отсекает
    # строку за один поиск, а массив в = ANY служит условием индекса под OR политики. Один
    # массив как фильтр перебирался бы целиком на каждой строке (тысячи поделённых id).
    hashed, listed = records.table.alias(), records.table.alias()
    mine = _member_orgs(user_id, within)
    shared_in_mine = select(hashed.c[records.resource]).where(hashed.c[records.org] == mine)
    shared_list = select(func.array_agg(listed.c[records.resource])).where(
        listed.c[records.org] == _member_orgs(user_id, within)
    )
    return and_(row_id.in_(shared_in_mine), row_id == any_(as_array(shared_list)), exact)


def sharing_workspaces(
    resource: ShareableResource, records: ShareRecords, user_id: UUID, ids: Collection[UUID]
) -> Select[UUID, UUID]:
    """The personal rows among `ids` of someone else that reach the viewer through a share,
    each with a workspace it is shared into that admits the viewer: the same rules as the
    share's predicate, as pairs of row and workspace."""
    table = resource.table
    row_id, owner = table.c[resource.id], table.c[resource.owner]
    share = records.table.alias()
    org = share.c[records.org]
    member, joined, conditions = _member_of(org, user_id)
    sharer = _table(Membership).alias()
    admits = level_admits(
        share.c[records.access], org, (records.grant_kind, share.c[records.grant_key]), member
    )
    filters = [
        row_id.in_(list(ids)),
        table.c[resource.org].is_(None),
        owner != user_id,
        sharer.c.state == MembershipState.ACTIVE,
        sharer.c.user_id == owner,
    ]
    if records.only is not None:
        column, value = records.only
        filters.append(share.c[column] == value)
    return (
        select(row_id, org)
        .select_from(table)
        .join(share, share.c[records.resource] == row_id)
        .join(sharer, sharer.c.id == share.c[records.sharer])
        .join(joined, true())
        .where(*filters, *conditions, admits)
        .order_by(row_id, org)
    )
