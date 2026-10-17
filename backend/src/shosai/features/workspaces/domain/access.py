"""Access levels, grantees and the cabinet's audiences (§7, ADR 0039 point 4, ADR 0053).

A workspace's row has an access level: `owner` (its owner alone), `selected` (the members
and teams granted it) or `organization` (every member but guests). The cabinet speaks of
audiences — participants, a team, the whole workspace — which map onto the levels; the
people a resource always admits (a meeting's participants who are members, whoever added
a knowledge item) become member grants. `level_admits` is the reference decision the SQL
predicate of the access policy must agree with; unknown levels admit nobody.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from shosai.features.workspaces.domain.roles import WorkspaceRole


class AccessLevel(StrEnum):
    """Who in the workspace may read a row of it (§7)."""

    OWNER = "owner"
    SELECTED = "selected"
    ORGANIZATION = "organization"


class GranteeKind(StrEnum):
    """Who a grant of a `selected` row names."""

    MEMBER = "member"
    TEAM = "team"


@dataclass(frozen=True, slots=True, order=True)
class Grantee:
    """One member (by membership id) or one team a row is granted to."""

    kind: GranteeKind
    id: UUID


class AudienceKind(StrEnum):
    """The cabinet's names for who sees a shared item."""

    PARTICIPANTS = "participants"
    TEAM = "team"
    WORKSPACE = "workspace"


@dataclass(frozen=True, slots=True)
class Audience:
    """An audience; a team audience names its team."""

    kind: AudienceKind
    team_id: UUID | None = None

    def __post_init__(self) -> None:
        if (self.kind is AudienceKind.TEAM) != (self.team_id is not None):
            message = "команда указывается у аудитории team и только у неё"
            raise ValueError(message)


class SharingDefault(StrEnum):
    """What a workspace does with a meeting whose participants are all its members."""

    PRIVATE = "private"
    PARTICIPANTS = "participants"
    WORKSPACE = "workspace"

    def audience(self) -> Audience | None:
        """The audience a meeting is shared with by default; None keeps it unshared."""
        match self:
            case SharingDefault.PRIVATE:
                return None
            case SharingDefault.PARTICIPANTS:
                return Audience(AudienceKind.PARTICIPANTS)
            case SharingDefault.WORKSPACE:
                return Audience(AudienceKind.WORKSPACE)


@dataclass(frozen=True, slots=True)
class Access:
    """A row's level and its grants."""

    level: AccessLevel
    grants: frozenset[Grantee] = frozenset()


def access_for(audience: Audience, always: Iterable[UUID]) -> Access:
    """The level and grants of an audience; `always` are members it admits in any case."""
    if audience.kind is AudienceKind.WORKSPACE:
        return Access(AccessLevel.ORGANIZATION)
    members = {Grantee(GranteeKind.MEMBER, member) for member in always}
    if audience.team_id is not None:
        members.add(Grantee(GranteeKind.TEAM, audience.team_id))
    return Access(AccessLevel.SELECTED, frozenset(members))


def audience_of(access: Access) -> Audience | None:
    """The audience the cabinet shows for a row; None for a row only its owner reads."""
    match access.level:
        case AccessLevel.ORGANIZATION:
            return Audience(AudienceKind.WORKSPACE)
        case AccessLevel.SELECTED:
            teams = sorted(grant.id for grant in access.grants if grant.kind is GranteeKind.TEAM)
            return (
                Audience(AudienceKind.TEAM, teams[0])
                if teams
                else Audience(AudienceKind.PARTICIPANTS)
            )
        case AccessLevel.OWNER:
            return None


@dataclass(frozen=True, slots=True)
class MemberView:
    """An active member reading a workspace's row: their membership, role and teams."""

    membership_id: UUID
    role: WorkspaceRole
    team_ids: frozenset[UUID]

    def grantees(self) -> frozenset[Grantee]:
        """Every grantee that admits this member."""
        teams = {Grantee(GranteeKind.TEAM, team) for team in self.team_ids}
        return frozenset({Grantee(GranteeKind.MEMBER, self.membership_id), *teams})


def level_admits(access: Access, member: MemberView) -> bool:
    """Whether a workspace's row admits an active member who does not own it.

    The owner of a row reads it whatever its level; the caller checks that first.
    """
    if access.level is AccessLevel.ORGANIZATION:
        return member.role is not WorkspaceRole.GUEST
    if access.level is AccessLevel.SELECTED:
        return not access.grants.isdisjoint(member.grantees())
    return False
