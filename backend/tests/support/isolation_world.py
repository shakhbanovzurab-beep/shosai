"""The canonical world of the isolation kit: two workspaces and the people that test §7's rules.

For one resource kind it holds workspace rows at every level, personal rows shared and not,
and the people each rule turns on: an owner, members, an admin of the other workspace, a
guest, a removed member, a hidden owner and a stranger. A kind with a named reader gets
rows naming each kind of person; a kind with a parent gets the parent kind's own world and
a child row under each parent, plus a child in the other workspace and one whose parent is
gone (ADR 0059).
"""

import uuid
from dataclasses import dataclass, field

from shosai.features.workspaces.infrastructure.share_records import SHARE_RECORDS
from tests.support.access_model import (
    GrantRow,
    MemberRow,
    ResourceRow,
    ShareRow,
    WorkspaceRow,
    World,
)


@dataclass(slots=True)
class Canon:
    """The canonical world's people, so a test can name who should see what."""

    world: World = field(default_factory=World)
    people: dict[str, uuid.UUID] = field(default_factory=dict)
    workspaces: dict[str, uuid.UUID] = field(default_factory=dict)
    # Членство человека в пространстве: (имя, пространство) → id членства.
    seats: dict[tuple[str, uuid.UUID], uuid.UUID] = field(default_factory=dict)
    team: uuid.UUID = field(default_factory=uuid.uuid4)

    def row(
        self,
        kind: str,
        owner: str,
        place: tuple[uuid.UUID | None, str | None],
        *,
        reader: str | None = None,
        parent: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Add a row of the kind in its place — a workspace and a level, or none — and its id."""
        row_id = uuid.uuid4()
        org, access = place
        named = self.people[reader] if reader is not None else None
        self.world.rows.append(
            ResourceRow(row_id, kind, self.people[owner], org, access, named, parent)
        )
        return row_id

    def grant(
        self, org: uuid.UUID, key: tuple[str, uuid.UUID], grantee: tuple[str, uuid.UUID]
    ) -> None:
        """Grant a row of a workspace to a member or a team."""
        self.world.grants.append(GrantRow(org, key[0], key[1], grantee[0], grantee[1]))


def canonical_world(kind: str, *, parent_kind: str | None = None, reader: bool = False) -> Canon:
    """Two workspaces and seven people covering every rule of §7 for one resource kind."""
    canon = _people()
    _rows_of(canon, kind)
    if reader:
        _reader_rows(canon, kind)
    if parent_kind is not None:
        _child_rows(canon, kind, parent_kind)
    return canon


def _people() -> Canon:
    canon = Canon()
    world, people = canon.world, canon.people
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    canon.workspaces.update(a=org_a, b=org_b)
    world.workspaces += [WorkspaceRow(org_a, "active"), WorkspaceRow(org_b, "active")]
    for name, org, role, state in (
        ("alice", org_a, "owner", "active"),
        ("bob", org_a, "member", "active"),
        ("carol", org_a, "member", "active"),
        ("carol", org_b, "admin", "active"),
        ("dan", org_a, "guest", "active"),
        ("erin", org_a, "member", "removed"),
        ("gina", org_a, "owner", "hidden"),
        ("frank", org_b, "owner", "active"),
    ):
        people.setdefault(name, uuid.uuid4())
        canon.seats[name, org] = uuid.uuid4()
        world.members.append(MemberRow(canon.seats[name, org], org, people[name], role, state))
    people["stranger"] = uuid.uuid4()
    seats = canon.seats
    world.teams[canon.team] = (org_a, frozenset({seats["bob", org_a], seats["erin", org_a]}))
    return canon


def _rows_of(canon: Canon, kind: str) -> None:
    """A kind's rows at every level, and personal rows shared and not."""
    org_a, org_b = canon.workspaces["a"], canon.workspaces["b"]
    canon.row(kind, "bob", (org_a, "organization"))
    canon.row(kind, "bob", (org_a, "owner"))
    canon.grant(org_a, (kind, canon.row(kind, "alice", (org_a, "selected"))), ("team", canon.team))
    selected = canon.row(kind, "alice", (org_a, "selected"))
    canon.grant(org_a, (kind, selected), ("member", canon.seats["carol", org_a]))
    canon.row(kind, "erin", (org_a, "organization"))
    canon.row(kind, "frank", (org_b, "organization"))
    canon.row(kind, "alice", (None, None))
    records = SHARE_RECORDS.get(kind)
    if records is None:
        return
    for owner, org, access, grantee in (
        ("alice", org_a, "organization", None),
        ("gina", org_a, "organization", None),
        ("carol", org_b, "selected", ("member", canon.seats["frank", org_b])),
        ("erin", org_a, "organization", None),
    ):
        shared = canon.row(kind, owner, (None, None))
        # Гранты встречи — под её id, гранты файла — под id элемента знаний.
        key = shared if records.grant_key == records.resource else uuid.uuid4()
        seat = canon.seats[owner, org]
        canon.world.shares.append(
            ShareRow(kind, shared, org, access, seat, records.grant_kind, key)
        )
        if grantee is not None:
            canon.grant(org, (records.grant_kind, key), grantee)


def _reader_rows(canon: Canon, kind: str) -> None:
    """Rows only their owner's level opens, each naming one kind of person as its reader."""
    org_a, org_b = canon.workspaces["a"], canon.workspaces["b"]
    for reader in ("carol", "dan", "erin", "frank", "gina"):
        canon.row(kind, "bob", (org_a, "owner"), reader=reader)
    canon.row(kind, "frank", (org_b, "owner"), reader="carol")


def _child_rows(canon: Canon, kind: str, parent_kind: str) -> None:
    """The parent kind's world, a child under each parent, a cross-workspace and an orphan child."""
    _rows_of(canon, parent_kind)
    shared_into = {share.resource_id: share.org_id for share in canon.world.shares}
    names = {user_id: name for name, user_id in canon.people.items()}
    parents = [row for row in canon.world.rows if row.kind == parent_kind]
    for parent in parents:
        org = parent.org_id or shared_into.get(parent.id)
        access = "owner" if org is not None else None
        canon.row(kind, names[parent.owner], (org, access), parent=parent.id)
    org_a, org_b = canon.workspaces["a"], canon.workspaces["b"]
    open_in_a = next(
        row.id for row in parents if row.org_id == org_a and row.access == "organization"
    )
    # Задача пространства B под встречей A: видна лишь участнику обоих, читающему встречу.
    canon.row(kind, "frank", (org_b, "owner"), parent=open_in_a)
    canon.row(kind, "bob", (org_a, "owner"), parent=uuid.uuid4())
