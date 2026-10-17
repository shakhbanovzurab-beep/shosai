"""What workspaces holds of a person, for identity's export, erasure and transfer (ADR 0053 p. 4).

A person's data here is their memberships. Erasing an account ends each membership the
way a removal does, in one transaction per workspace: if the person was its only owner,
ownership passes to the longest-standing admin, else member; a workspace nobody else
belongs to is deleted with the account. The row stays as `removed` with its title
cleared — the company's history, holding ids only. An account with a standing membership
does not move between homes: identity refuses the request, and `copy` refuses again.
"""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import Table, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.db.person_rows import PersonRows, person_lines
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.contracts import AuditAction, AuditEntry, AuditLog
from shosai.features.workspaces.contracts.events import (
    MemberRemoved,
    MemberRoleChanged,
    WorkspaceDeleted,
)
from shosai.features.workspaces.domain.memberships import (
    STANDING,
    MembershipState,
    RemovalReason,
    RosterChange,
    RosterEntry,
    apply_change,
    keeps_an_owner,
    successor,
)
from shosai.features.workspaces.domain.roles import WorkspaceRole
from shosai.features.workspaces.infrastructure.member_withdrawal import withdraw_member
from shosai.features.workspaces.infrastructure.membership_reader import MembershipDirectory
from shosai.features.workspaces.infrastructure.organization_records import (
    Membership,
    Organization,
)

OWNER: Final = "workspaces"
EXPORTED = PersonRows(
    cast("Table", Membership.__table__),
    ("org_id", "role", "state", "title", "joined_at", "removed_at", "removal_reason"),
    key="id",
)
ROSTER_COLUMNS = (
    Membership.id,
    Membership.user_id,
    Membership.role,
    Membership.state,
    Membership.joined_at,
)
# Строка человека ещё что-то держит: членство не закончено или осталась должность.
HELD = or_(Membership.state != MembershipState.REMOVED, Membership.title.is_not(None))


@dataclass(frozen=True, slots=True)
class Departure:
    """One membership ending: its workspace, the roster around it and whose seat is whose."""

    org_id: UUID
    membership_id: UUID
    user_id: UUID
    roster: tuple[RosterEntry, ...]
    users: Mapping[UUID, UUID]


class MembershipBlocksTransferError(RuntimeError):
    """The account belongs to a workspace and cannot move between homes (ADR 0053 point 4)."""


class WorkspacesAccountData:
    """Exports, erases and refuses to move a person's memberships."""

    def __init__(
        self, transactions: HomeTransactions, outbox: EventOutbox, audit: AuditLog
    ) -> None:
        self._transactions = transactions
        self._outbox = outbox
        self._audit = audit

    @property
    def owner(self) -> str:
        """The owner of workspaces' declaration in the deletion registry."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """The person's memberships, every state, as one JSON Lines file."""
        scope = TenancyScope(account.home, account.user_id)
        yield ExportFile(
            "memberships.jsonl", person_lines(self._transactions, scope, EXPORTED, account.user_id)
        )

    async def erase(self, account: AccountRef) -> None:
        """End every membership of the person; a repeat changes nothing."""
        for org_id in await self._held(account):
            await self._leave(account, org_id)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """Refuse while the person belongs to a workspace; otherwise nothing moves.

        Removed memberships are the companies' history and stay in their home.
        """
        async with self._transactions.begin(TenancyScope(account.home, account.user_id)) as session:
            if await MembershipDirectory().has_memberships(session, account.user_id):
                message = f"аккаунт состоит в пространствах и не переезжает в дом {to_home.value}"
                raise MembershipBlocksTransferError(message)

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """Nothing of workspaces moves with an account, so nothing is compared."""
        return {}

    async def purge(self, account: AccountRef) -> None:
        """Nothing of workspaces moved, so nothing is purged."""

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """`memberships` while a membership of the erased account still holds anything."""
        return ("memberships",) if await self._held(account) else ()

    async def _held(self, account: AccountRef) -> list[UUID]:
        scope = TenancyScope(account.home, account.user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            found = await session.scalars(
                select(Membership.org_id).where(Membership.user_id == account.user_id, HELD)
            )
            return list(found)

    async def _leave(self, account: AccountRef, org_id: UUID) -> None:
        async with self._transactions.begin(TenancyScope(account.home, org_id=org_id)) as session:
            query = select(*ROSTER_COLUMNS).where(Membership.org_id == org_id).with_for_update()
            rows = (await session.execute(query)).all()
            mine = next((row for row in rows if row[1] == account.user_id), None)
            if mine is None:
                return
            if MembershipState(mine[3]) is MembershipState.REMOVED:
                cleared = update(Membership).where(Membership.id == mine[0]).values(title=None)
                await session.execute(cleared)
                return
            departure = Departure(
                org_id=org_id,
                membership_id=mine[0],
                user_id=account.user_id,
                roster=tuple(
                    RosterEntry(row[0], WorkspaceRole(row[2]), MembershipState(row[3]), row[4])
                    for row in rows
                ),
                users={row[0]: row[1] for row in rows},
            )
            await self._end(session, departure)

    async def _end(self, session: AsyncSession, departure: Departure) -> None:
        org_id, membership_id = departure.org_id, departure.membership_id
        leaving = RosterChange(membership_id, state=MembershipState.REMOVED)
        roster = departure.roster
        if not keeps_an_owner(roster, leaving):
            heir = successor(roster, membership_id)
            if heir is None:
                # Больше никого нет: пространство уходит вместе с аккаунтом; строки — каскадом.
                await session.execute(delete(Organization).where(Organization.id == org_id))
                await self._outbox.add(session, WorkspaceDeleted(org_id=org_id))
                return
            await self._hand_over(session, org_id, heir)
            roster = apply_change(roster, RosterChange(heir, role=WorkspaceRole.OWNER))
        await session.execute(
            update(Membership)
            .where(Membership.id == membership_id)
            .values(
                state=MembershipState.REMOVED,
                removed_at=datetime.now(UTC),
                removal_reason=RemovalReason.ACCOUNT_ERASED,
                title=None,
            )
        )
        await withdraw_member(session, org_id, membership_id)
        reason = RemovalReason.ACCOUNT_ERASED
        await self._record(session, org_id, AuditAction.MEMBER_REMOVED, membership_id, reason)
        # Созданное человеком в пространстве переходит к владельцу (nfr-16): старейшему из них.
        owner = min(
            (
                e
                for e in apply_change(roster, leaving)
                if e.role is WorkspaceRole.OWNER and e.state in STANDING
            ),
            key=lambda entry: entry.joined_at,
        )
        event = MemberRemoved(
            org_id=org_id,
            user_id=departure.user_id,
            membership_id=membership_id,
            reason=reason,
            successor_user_id=departure.users[owner.membership_id],
        )
        await self._outbox.add(session, event)

    async def _hand_over(self, session: AsyncSession, org_id: UUID, heir: UUID) -> None:
        """Make the heir the workspace's owner, with its audit row and event."""
        promote = update(Membership).where(Membership.id == heir).values(role=WorkspaceRole.OWNER)
        await session.execute(promote)
        await self._record(session, org_id, AuditAction.OWNER_TRANSFERRED, heir, None)
        changed = MemberRoleChanged(org_id=org_id, membership_id=heir, role=WorkspaceRole.OWNER)
        await self._outbox.add(session, changed)

    async def _record(
        self,
        session: AsyncSession,
        org_id: UUID,
        action: AuditAction,
        target: UUID,
        value: str | None,
    ) -> None:
        entry = AuditEntry(org_id, action, None, "membership", target, value)
        await self._audit.record(session, entry)
