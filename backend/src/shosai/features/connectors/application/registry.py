"""The `connectors.connections` binding: what a consumer may know of connections (§3.3).

Every read runs in the caller's transaction and under its row-level security, and returns
views without a secret. A person's connection serves a workspace only while its person is an
active member there (CN-D3); a workspace's own installation always serves it.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.contracts import ConnectionView
from shosai.features.connectors.domain.catalogue import CATALOGUE, App, Capability
from shosai.features.connectors.infrastructure.store.connection_reads import binding, bindings
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord
from shosai.features.workspaces.contracts import MEMBERSHIP_READER


class ConnectorRegistry:
    """Reads of connections for consumers."""

    def __init__(self, ports: PortDirectory) -> None:
        self._ports = ports

    async def of_person(
        self, session: AsyncSession, user_id: UUID, capability: Capability | None = None
    ) -> tuple[ConnectionView, ...]:
        """The person's own connections, of one capability or all."""
        conditions = [ConnectionRecord.user_id == user_id, ConnectionRecord.org_id.is_(None)]
        if capability is not None:
            apps = [app.value for app, spec in CATALOGUE.items() if spec.capability is capability]
            conditions.append(ConnectionRecord.app.in_(apps))
        return tuple(found.view for found in await bindings(session, *conditions))

    async def of_workspace(
        self, session: AsyncSession, org_id: UUID, app: App
    ) -> tuple[ConnectionView, ...]:
        """A workspace's installations of one app."""
        found = await bindings(
            session, ConnectionRecord.org_id == org_id, ConnectionRecord.app == app.value
        )
        return tuple(item.view for item in found)

    async def get(self, session: AsyncSession, connection_id: UUID) -> ConnectionView | None:
        """One connection the scope may read, or None."""
        found = await binding(session, connection_id)
        return None if found is None else found.view

    async def usable_for(self, session: AsyncSession, connection_id: UUID, org_id: UUID) -> bool:
        """Whether the connection may serve the workspace now."""
        found = await binding(session, connection_id)
        if found is None:
            return False
        if found.view.org_id is not None:
            return found.view.org_id == org_id
        memberships = await self._ports.get(MEMBERSHIP_READER).active(session, found.view.user_id)
        return any(membership.org_id == org_id for membership in memberships)
