"""Workspaces' services over the run's slot, with billing's seats played by a double."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.workspaces.application.admission import Admission
from shosai.features.workspaces.application.lifecycle import CreatedWorkspace, Lifecycle
from shosai.features.workspaces.application.members import Members
from shosai.features.workspaces.application.teams import Teams
from shosai.features.workspaces.contracts import SEAT_ALLOWANCE, PaidSeats
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.harness.connections import Connection, fetch_rows
from tests.harness.database_access import DatabaseAccess


@dataclass(slots=True)
class FixedSeats:
    """Billing's seats as a test sets them: the same number for every workspace."""

    paid: int
    trials: list[tuple[uuid.UUID, int]] = field(default_factory=list)

    async def seats(self, _session: AsyncSession, _org_id: uuid.UUID) -> PaidSeats:
        return PaidSeats(self.paid, None)

    async def start_trial(self, _session: AsyncSession, org_id: uuid.UUID, seats: int) -> PaidSeats:
        self.trials.append((org_id, seats))
        self.paid = seats
        return PaidSeats(seats, None)


@dataclass(frozen=True, slots=True)
class Services:
    lifecycle: Lifecycle
    admission: Admission
    members: Members
    teams: Teams


def ports_with(seats: FixedSeats | None) -> PortDirectory:
    """Ports with billing's seats bound, or with nothing bound."""
    ports = PortDirectory()
    ports.install([SEAT_ALLOWANCE.bind(seats)] if seats is not None else [])
    return ports


def services(homes: DatabaseAccess, seats: FixedSeats | None) -> Services:
    outbox, audit, ports = (
        EventOutbox(EventTypes(list(WORKSPACES.events))),
        WorkspaceAuditLog(),
        ports_with(seats),
    )
    return Services(
        Lifecycle(homes.transactions, outbox, audit, ports),
        Admission(homes.transactions, outbox, audit, ports),
        Members(homes.transactions, outbox, audit),
        Teams(homes.transactions, outbox, audit),
    )


async def created(
    found: Services, home: Home, owner: uuid.UUID, name: str = "Acme"
) -> CreatedWorkspace:
    """A workspace the owner created in their home."""
    return await found.lifecycle.create(TenancyScope(home, owner), name, seats=5)


async def audit_actions(connection: Connection) -> list[str]:
    rows = await fetch_rows(
        connection, "SELECT action FROM org_audit_events ORDER BY created_at, action"
    )
    return [row["action"] for row in rows]


async def event_types(connection: Connection) -> list[str]:
    rows = await fetch_rows(
        connection, "SELECT event_type FROM outbox_messages ORDER BY occurred_at, id"
    )
    return [row["event_type"] for row in rows]
