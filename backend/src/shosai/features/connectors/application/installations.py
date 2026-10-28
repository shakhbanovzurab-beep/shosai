"""A workspace's installations of an app into a provider's tenant (chats' Slack, CN-D3).

An admin starts one from the consumer's own screen; the flow returns to chats' callback page
with the installation's id, which is its connection's. Removing it ends the connection with
an audit row and `connectors.connection.revoked`, and leaves its grant for revocation when
no app is left on it (plan step 4).
"""

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.features.connectors.application.authorize import Authorizer, ConnectRequest
from shosai.features.connectors.application.installation_audit import InstallationAudit
from shosai.features.connectors.contracts import Handoff, NotConnectedError
from shosai.features.connectors.contracts.events import ConnectionRevoked, RevokeReason
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.domain.flows import ReturnKind, ReturnTarget
from shosai.features.connectors.infrastructure.store.grant_writes import retire_if_orphaned
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord


class WorkspaceInstallations:
    """The `connectors.installations` binding."""

    def __init__(
        self, authorizer: Authorizer, audit: InstallationAudit, outbox: EventOutbox
    ) -> None:
        self._authorizer = authorizer
        self._audit = audit
        self._outbox = outbox

    async def begin(self, home: Home, org_id: UUID, admin_user_id: UUID, app: App) -> Handoff:
        """Start an installation; the callback checks the admin's role again."""
        request = ConnectRequest(
            user_id=admin_user_id, home=home, app=app, target=ReturnTarget(ReturnKind.CHATS),
            org_id=org_id,
        )  # fmt: skip
        return await self._authorizer.begin(request)

    async def remove(self, session: AsyncSession, org_id: UUID, connection_id: UUID) -> None:
        """End an installation in the caller's transaction."""
        statement = (
            delete(ConnectionRecord)
            .where(ConnectionRecord.id == connection_id, ConnectionRecord.org_id == org_id)
            .returning(ConnectionRecord.grant_id, ConnectionRecord.app, ConnectionRecord.user_id)
        )
        removed = (await session.execute(statement)).first()
        if removed is None:
            raise NotConnectedError
        await retire_if_orphaned(session, removed.grant_id)
        app = App(removed.app)
        await self._audit.removed(session, org_id, (None, connection_id, app))
        await self._outbox.add(
            session,
            ConnectionRevoked(
                connection_id=connection_id, user_id=removed.user_id, org_id=org_id, app=app,
                reason=RevokeReason.DISCONNECTED,
            ),
        )  # fmt: skip
