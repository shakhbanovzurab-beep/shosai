"""A workspace's life: created with its owner and trial, suspended and resumed (§3.6).

Creation needs billing's seats: until billing binds its port no workspace is created
(ADR 0053 point 7). The slug is taken once from the name, the first candidate free in
the home; the unique index decides, since row-level security hides other workspaces.
Suspension keeps everything and closes the workspace to its members (423) until resumed.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from itertools import islice
from typing import Final
from uuid import UUID

from sqlalchemy import insert, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.workspaces.contracts import SEAT_ALLOWANCE, AuditAction, AuditEntry, AuditLog
from shosai.features.workspaces.contracts.events import (
    JoinChannel,
    MemberJoined,
    SuspensionSource,
    WorkspaceCreated,
    WorkspaceResumed,
    WorkspaceSuspended,
)
from shosai.features.workspaces.domain.roles import WorkspaceRole
from shosai.features.workspaces.domain.seats import seats_at_creation_valid
from shosai.features.workspaces.domain.slugs import slug_candidates
from shosai.features.workspaces.infrastructure.organization_records import (
    Membership,
    Organization,
)

# Столько кандидатов «имя», «имя-2», … пробуется, прежде чем отказать.
SLUG_ATTEMPTS: Final = 50


@dataclass(frozen=True, slots=True)
class CreatedWorkspace:
    """A new workspace: its id, slug and its owner's membership."""

    org_id: UUID
    slug: str
    membership_id: UUID


class Lifecycle:
    """Creates, suspends and resumes workspaces."""

    def __init__(
        self,
        transactions: HomeTransactions,
        outbox: EventOutbox,
        audit: AuditLog,
        ports: PortDirectory,
    ) -> None:
        self._transactions = transactions
        self._outbox = outbox
        self._audit = audit
        self._ports = ports

    async def create(self, scope: TenancyScope, name: str, seats: int) -> CreatedWorkspace:
        """A workspace in the person's home with them as its owner and billing's trial."""
        if scope.user_id is None or scope.org_id is not None:
            message = "пространство создаёт человек, в скоупе без пространства"
            raise ValueError(message)
        if not seats_at_creation_valid(seats):
            raise AppError("seats_invalid", HTTPStatus.UNPROCESSABLE_ENTITY)
        allowances = self._ports.all(SEAT_ALLOWANCE)
        if not allowances:
            raise AppError("seats_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)
        org_id, membership_id = new_id(), new_id()
        owner = scope.user_id
        async with self._transactions.begin(TenancyScope(scope.home, owner, org_id)) as session:
            slug = await _claim_slug(session, org_id, name, owner)
            await session.execute(
                insert(Membership).values(
                    id=membership_id, org_id=org_id, user_id=owner, role=WorkspaceRole.OWNER
                )
            )
            await allowances[0].start_trial(session, org_id, seats)
            entry = AuditEntry(
                org_id, AuditAction.WORKSPACE_CREATED, membership_id, "workspace", org_id
            )
            await self._audit.record(session, entry)
            await self._outbox.add(session, WorkspaceCreated(org_id=org_id, owner_user_id=owner))
            joined = MemberJoined(
                org_id=org_id, user_id=owner, membership_id=membership_id, via=JoinChannel.CREATED
            )
            await self._outbox.add(session, joined)
        return CreatedWorkspace(org_id, slug, membership_id)

    async def suspend(self, scope: TenancyScope, source: SuspensionSource, reason: str) -> None:
        """Close the workspace to its members; nothing is deleted (the platform or billing)."""
        org_id = _org_of(scope)
        async with self._transactions.begin(scope) as session:
            changed = await session.scalar(
                update(Organization)
                .where(Organization.id == org_id, Organization.state == "active")
                .values(state="suspended", suspended_at=datetime.now(UTC), suspension_reason=reason)
                .returning(Organization.id)
            )
            if changed is None:
                raise AppError("workspace_not_active", HTTPStatus.CONFLICT)
            entry = AuditEntry(org_id, AuditAction.SUSPENDED, None, "workspace", org_id, source)
            await self._audit.record(session, entry)
            await self._outbox.add(session, WorkspaceSuspended(org_id=org_id, source=source))

    async def resume(self, scope: TenancyScope) -> None:
        """Open a suspended workspace again, exactly as it was."""
        org_id = _org_of(scope)
        async with self._transactions.begin(scope) as session:
            changed = await session.scalar(
                update(Organization)
                .where(Organization.id == org_id, Organization.state == "suspended")
                .values(state="active", suspended_at=None, suspension_reason=None)
                .returning(Organization.id)
            )
            if changed is None:
                raise AppError("workspace_not_suspended", HTTPStatus.CONFLICT)
            entry = AuditEntry(org_id, AuditAction.RESUMED, None, "workspace", org_id)
            await self._audit.record(session, entry)
            await self._outbox.add(session, WorkspaceResumed(org_id=org_id))


def _org_of(scope: TenancyScope) -> UUID:
    if scope.org_id is None:
        message = "смена состояния пространства идёт в его скоупе"
        raise ValueError(message)
    return scope.org_id


async def _claim_slug(session: AsyncSession, org_id: UUID, name: str, owner: UUID) -> str:
    """Insert the workspace under the first free slug; the unique index arbitrates."""
    for slug in islice(slug_candidates(name), SLUG_ATTEMPTS):
        claimed = await session.scalar(
            upsert(Organization)
            .values(id=org_id, slug=slug, name=name, created_by=owner)
            .on_conflict_do_nothing(index_elements=[Organization.slug])
            .returning(Organization.slug)
        )
        if claimed is not None:
            return str(claimed)
    raise AppError("slug_taken", HTTPStatus.CONFLICT)
