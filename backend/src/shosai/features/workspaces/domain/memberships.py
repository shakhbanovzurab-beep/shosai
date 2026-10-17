"""A membership's life, the last-owner rule and who inherits a workspace (§7, ADR 0053 point 4).

A membership is `active`, `hidden` while identity's deletion window hides the person's
account, or `removed`. A hidden member keeps their seat and their role, so a cancelled
deletion restores everything unchanged; a removed row is kept (§8.1) and becomes active
again only through a new join.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.features.workspaces.domain.roles import WorkspaceRole


class MembershipState(StrEnum):
    """Where a membership is in its life."""

    ACTIVE = "active"
    # Аккаунт человека в окне удаления: место и роль сохраняются, доступа нет.
    HIDDEN = "hidden"
    REMOVED = "removed"


class RemovalReason(StrEnum):
    """Why a membership ended."""

    REMOVED_BY_ADMIN = "removed_by_admin"
    LEFT = "left"
    ACCOUNT_ERASED = "account_erased"
    WORKSPACE_DELETED = "workspace_deleted"


# Состояния, которые держат место и роль: владелец в окне удаления остаётся владельцем.
STANDING: Final = frozenset({MembershipState.ACTIVE, MembershipState.HIDDEN})
TRANSITIONS: Final[dict[MembershipState, frozenset[MembershipState]]] = {
    MembershipState.ACTIVE: frozenset({MembershipState.HIDDEN, MembershipState.REMOVED}),
    MembershipState.HIDDEN: frozenset({MembershipState.ACTIVE, MembershipState.REMOVED}),
    # Снова в пространство — только новым вступлением, по приглашению или домену.
    MembershipState.REMOVED: frozenset({MembershipState.ACTIVE}),
}


class MembershipTransitionError(ValueError):
    """A membership cannot move from its state to the requested one."""


def check_transition(current: MembershipState, target: MembershipState) -> None:
    """Refuse a move the membership's life does not allow."""
    if target not in TRANSITIONS[current]:
        message = f"членство не переходит из {current} в {target}"
        raise MembershipTransitionError(message)


@dataclass(frozen=True, slots=True)
class RosterEntry:
    """One membership of a workspace, as the last-owner rule and succession see it."""

    membership_id: UUID
    role: WorkspaceRole
    state: MembershipState
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class RosterChange:
    """A proposed change of one membership: a new role, a new state, or both."""

    membership_id: UUID
    role: WorkspaceRole | None = None
    state: MembershipState | None = None


def apply_change(roster: Iterable[RosterEntry], change: RosterChange) -> tuple[RosterEntry, ...]:
    """The roster as it would be after the change."""
    return tuple(
        RosterEntry(
            membership_id=entry.membership_id,
            role=change.role or entry.role,
            state=change.state or entry.state,
            joined_at=entry.joined_at,
        )
        if entry.membership_id == change.membership_id
        else entry
        for entry in roster
    )


def has_owner(roster: Iterable[RosterEntry]) -> bool:
    """Whether a standing member owns the workspace."""
    return any(entry.role is WorkspaceRole.OWNER and entry.state in STANDING for entry in roster)


def keeps_an_owner(roster: Iterable[RosterEntry], change: RosterChange) -> bool:
    """Whether the workspace still has an owner after the change (§7: the last owner stays)."""
    return has_owner(apply_change(roster, change))


def successor(roster: Iterable[RosterEntry], leaving: UUID) -> UUID | None:
    """Who owns the workspace when its only owner's account is erased (ADR 0053 point 4).

    The longest-standing active admin, else the longest-standing active member; guests
    and hidden members never inherit. None means nobody is left and the workspace goes
    with the account.
    """
    candidates = [
        entry
        for entry in roster
        if entry.membership_id != leaving
        and entry.state is MembershipState.ACTIVE
        and entry.role in {WorkspaceRole.ADMIN, WorkspaceRole.MEMBER}
    ]
    if not candidates:
        return None
    # Сначала админы, затем по стажу; равный стаж разводит id, чтобы ответ был один.
    chosen = min(
        candidates,
        key=lambda entry: (
            entry.role is not WorkspaceRole.ADMIN,
            entry.joined_at,
            entry.membership_id,
        ),
    )
    return chosen.membership_id


class OwnershipTransferError(ValueError):
    """Ownership cannot pass to the chosen membership."""


def ownership_transfer(roster: Iterable[RosterEntry], to: UUID) -> tuple[RosterChange, ...]:
    """The changes that give the workspace to an active member; previous owners become admins.

    The cabinet's admin action for when the owner left the company or cannot be reached.
    """
    entries = tuple(roster)
    target = next((entry for entry in entries if entry.membership_id == to), None)
    if target is None or target.state is not MembershipState.ACTIVE:
        message = "владение передаётся только действующему участнику"
        raise OwnershipTransferError(message)
    if target.role in {WorkspaceRole.OWNER, WorkspaceRole.GUEST}:
        message = f"владение не передаётся участнику с ролью {target.role}"
        raise OwnershipTransferError(message)
    previous = tuple(
        RosterChange(entry.membership_id, role=WorkspaceRole.ADMIN)
        for entry in entries
        if entry.role is WorkspaceRole.OWNER
    )
    return (*previous, RosterChange(to, role=WorkspaceRole.OWNER))
