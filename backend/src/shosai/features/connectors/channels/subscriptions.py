"""Connectors' consumer of workspaces' events: a deleted workspace's installations go.

Until workspaces' deletion saga calls each slice's workspace data handler (workspaces plan
step 11), connectors follows `workspaces.workspace.deleted`: in the workspace's scope, every
installation of it ends with `connectors.connection.revoked` (`workspace_deleted`), and its
grants are left for the provider's revocation. A redelivery finds nothing more to end.
"""

from datetime import timedelta
from typing import Any, Final

import structlog
from sqlalchemy import delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.queues import TaskQueue
from shosai.features.connectors.contracts.events import ConnectionRevoked, RevokeReason
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.domain.states import GrantStatus
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord, GrantRecord
from shosai.features.workspaces.contracts.events import WorkspaceDeleted

DEADLINE: Final = timedelta(seconds=60)
log = structlog.stdlib.get_logger(__name__)


def scope_of_workspace(event: WorkspaceDeleted, scope: TenancyScope) -> TenancyScope:
    """The deleted workspace's own scope in the event's home."""
    return TenancyScope(scope.home, org_id=event.org_id)


def subscriptions(outbox: EventOutbox) -> tuple[EventSubscription[Any], ...]:
    """The subscriptions bound to the process's outbox."""

    async def workspace_deleted(
        session: AsyncSession, received: ReceivedEvent[WorkspaceDeleted]
    ) -> None:
        org_id = received.event.org_id
        ended = await session.execute(
            delete(ConnectionRecord)
            .where(ConnectionRecord.org_id == org_id)
            .returning(ConnectionRecord.id, ConnectionRecord.user_id, ConnectionRecord.app)
        )
        events = [
            ConnectionRevoked(
                connection_id=row.id, user_id=row.user_id, org_id=org_id, app=App(row.app),
                reason=RevokeReason.WORKSPACE_DELETED,
            )
            for row in ended
        ]  # fmt: skip
        await session.execute(
            update(GrantRecord)
            .where(GrantRecord.org_id == org_id, GrantRecord.status != GrantStatus.REVOKING.value)
            .values(
                status=GrantStatus.REVOKING.value, problem=None, revoke_at=func.now(),
                updated_at=func.now(),
            )
        )  # fmt: skip
        if events:
            await outbox.add_all(session, events)
        log.info("Установки удалённого пространства сняты", installations=len(events))

    return (
        EventSubscription(
            consumer="connectors.workspace_erase", event=WorkspaceDeleted,
            queue=TaskQueue.DEFAULT, deadline=DEADLINE, handle=workspace_deleted,
            scope=scope_of_workspace,
        ),
    )  # fmt: skip
