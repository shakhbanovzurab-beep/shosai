"""The access rules of §7 in plain Python: the oracle the SQL policy is compared with.

A world holds workspaces, memberships, teams, rows of shareable resources, grants and
share records; a workspace's row may name a reader and a parent row (ADR 0059).
`readable` and `manageable` answer from the rules of the plan (§3.5) and the cabinet's
access notes, written independently of the SQL predicates.
"""

from dataclasses import dataclass, field
from uuid import UUID

MANAGERS = frozenset({"owner", "admin"})


@dataclass(frozen=True, slots=True)
class WorkspaceRow:
    id: UUID
    state: str  # active | suspended


@dataclass(frozen=True, slots=True)
class MemberRow:
    id: UUID
    org_id: UUID
    user_id: UUID
    role: str
    state: str  # active | hidden | removed


@dataclass(frozen=True, slots=True)
class ResourceRow:
    id: UUID
    kind: str
    owner: UUID
    org_id: UUID | None
    access: str | None
    # Участник, которому строка пространства видна всегда (исполнитель задачи).
    reader: UUID | None = None
    # Родительская строка другого вида: её читатели видят и эту строку пространства.
    parent: UUID | None = None


@dataclass(frozen=True, slots=True)
class ShareRow:
    """A personal row shared into a workspace, with the key its grants are filed under."""

    kind: str
    resource_id: UUID
    org_id: UUID
    access: str
    sharer: UUID
    grant_kind: str
    grant_key: UUID


@dataclass(frozen=True, slots=True)
class GrantRow:
    org_id: UUID
    resource_kind: str
    resource_id: UUID
    grantee_kind: str
    grantee_id: UUID


@dataclass(slots=True)
class World:
    workspaces: list[WorkspaceRow] = field(default_factory=list)
    members: list[MemberRow] = field(default_factory=list)
    # Команда → её пространство и участники (id членств).
    teams: dict[UUID, tuple[UUID, frozenset[UUID]]] = field(default_factory=dict)
    rows: list[ResourceRow] = field(default_factory=list)
    shares: list[ShareRow] = field(default_factory=list)
    grants: list[GrantRow] = field(default_factory=list)

    def active_member(self, org_id: UUID, user_id: UUID) -> MemberRow | None:
        workspace = next((w for w in self.workspaces if w.id == org_id), None)
        if workspace is None or workspace.state != "active":
            return None
        return next(
            (
                m
                for m in self.members
                if m.org_id == org_id and m.user_id == user_id and m.state == "active"
            ),
            None,
        )

    def admits(
        self, org_id: UUID, level: str | None, grant: tuple[str, UUID], member: MemberRow
    ) -> bool:
        if level == "organization":
            return member.role != "guest"
        if level != "selected":
            return False
        teams = {team for team, (_, people) in self.teams.items() if member.id in people}
        kind, key = grant
        return any(
            g.org_id == org_id
            and g.resource_kind == kind
            and g.resource_id == key
            and (
                (g.grantee_kind == "member" and g.grantee_id == member.id)
                or (g.grantee_kind == "team" and g.grantee_id in teams)
            )
            for g in self.grants
        )


def readable(world: World, kind: str, user_id: UUID, within: UUID | None = None) -> set[UUID]:
    """The rows of a kind the person may read; `within` narrows to one workspace."""
    return {
        row.id
        for row in world.rows
        if row.kind == kind and _sees(world, row, user_id, within, manage=False)
    }


def manageable(world: World, kind: str, user_id: UUID) -> set[UUID]:
    """The rows of a kind whose access the person may change."""
    return {
        row.id
        for row in world.rows
        if row.kind == kind and _sees(world, row, user_id, None, manage=True)
    }


def _sees(
    world: World, row: ResourceRow, user_id: UUID, within: UUID | None, *, manage: bool
) -> bool:
    if row.org_id is not None:
        in_view = within is None or row.org_id == within
        level = (row.access, (row.kind, row.id))
        people = (row.owner, user_id)
        admitted = _admitted(world, row.org_id, people, level, manage=manage)
        widened = not manage and _widened(world, row, user_id, within)
        return in_view and (admitted or widened)
    if row.owner == user_id and (within is None or manage):
        return True
    return any(
        share.kind == row.kind
        and share.resource_id == row.id
        and (within is None or share.org_id == within)
        and _sharer_stands(world, share, row.owner)
        and _admitted(
            world,
            share.org_id,
            (row.owner, user_id),
            (share.access, (share.grant_kind, share.grant_key)),
            manage=manage,
        )
        for share in world.shares
    )


def _widened(world: World, row: ResourceRow, user_id: UUID, within: UUID | None) -> bool:
    """An active member of the row's workspace it names, or who may read its parent now."""
    if row.org_id is None or world.active_member(row.org_id, user_id) is None:
        return False
    if row.reader == user_id:
        return True
    parent = next((other for other in world.rows if other.id == row.parent), None)
    return parent is not None and _sees(world, parent, user_id, within, manage=False)


def _sharer_stands(world: World, share: ShareRow, owner: UUID) -> bool:
    """The member who shared is the row's owner and still an active member."""
    sharer = next((m for m in world.members if m.id == share.sharer), None)
    return sharer is not None and sharer.state == "active" and sharer.user_id == owner


def _admitted(
    world: World,
    org_id: UUID,
    people: tuple[UUID, UUID],
    level: tuple[str | None, tuple[str, UUID]],
    *,
    manage: bool,
) -> bool:
    """An active member of an active workspace: the owner always, others at the level.

    `people` is the row's owner and the person reading.
    """
    owner, user_id = people
    member = world.active_member(org_id, user_id)
    if member is None:
        return False
    if owner == user_id:
        return True
    access, grant = level
    allowed_role = not manage or member.role in MANAGERS
    return allowed_role and world.admits(org_id, access, grant, member)
