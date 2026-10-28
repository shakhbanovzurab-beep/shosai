"""The events connectors publishes (connectors plan §3.3): ids, the app and codes only.

One event per connection: a grant that breaks emits `connectors.connection.broken` for each
of its apps, so a consumer follows the apps it uses and never needs to know about grants.
`broken` is emitted once per transition into needing the person (CN-D11); `connected` with
`reconnected` when a broken or replaced connection works again.
"""

from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from shosai.core.events.domain_event import DomainEvent
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.domain.states import Problem


class RevokeReason(StrEnum):
    """Why a connection ended."""

    DISCONNECTED = "disconnected"
    REPLACED = "replaced"
    ERASED = "erased"
    WORKSPACE_DELETED = "workspace_deleted"
    PROVIDER_CLOSED = "provider_closed"


class ConnectionConnected(DomainEvent):
    """An app works for its person or workspace: new, or working again."""

    event_type: ClassVar[str] = "connectors.connection.connected"
    version: ClassVar[int] = 1
    connection_id: UUID
    user_id: UUID
    org_id: UUID | None = None
    app: App
    reconnected: bool = False


class ConnectionBroken(DomainEvent):
    """An app newly needs its person; the problem names the repair."""

    event_type: ClassVar[str] = "connectors.connection.broken"
    version: ClassVar[int] = 1
    connection_id: UUID
    user_id: UUID
    org_id: UUID | None = None
    app: App
    problem: Problem


class ConnectionRevoked(DomainEvent):
    """An app's connection ended; every consumer stops using it at once."""

    event_type: ClassVar[str] = "connectors.connection.revoked"
    version: ClassVar[int] = 1
    connection_id: UUID
    user_id: UUID
    org_id: UUID | None = None
    app: App
    reason: RevokeReason


CONNECTOR_EVENTS: tuple[type[DomainEvent], ...] = (
    ConnectionConnected,
    ConnectionBroken,
    ConnectionRevoked,
)
