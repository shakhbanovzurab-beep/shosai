"""What other slices may use of connectors (connectors plan §3.3, ADR 0075).

`CONNECTIONS` tells a consumer which connections a person or a workspace has and in what
state — never a token. `PROVIDER_ACCESS` opens a `ProviderSession` on one connection: the
token injected, refreshed when it expires and once on a 401, the provider's limits and
`Retry-After` kept; tasks calls Jira through it, and connectors' own adapters behind the
capability ports call every other provider through it (CN-D1). `INSTALLATIONS` lets chats
install Slack into a workspace; an installation's id is its connection's. A consumer
declares the apps it uses through `CONNECTOR_USES`, and the catalogue offers only those
(CN-D4). The events are in `contracts.events`; the capability ports arrive with the
provider step that first implements each.
"""

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import Cardinality, PortKey
from shosai.features.connectors.contracts.provider import (
    ProviderBusyError,
    ProviderCall,
    ProviderRefusedError,
    ProviderResponse,
    ProviderSession,
    ProviderUnavailableError,
)
from shosai.features.connectors.domain.catalogue import App, Capability, Owner
from shosai.features.connectors.domain.states import ConnectionStatus, Problem

__all__ = [
    "CONNECTIONS",
    "CONNECTOR_USES",
    "INSTALLATIONS",
    "PROVIDER_ACCESS",
    "App",
    "Capability",
    "ConnectionRegistry",
    "ConnectionStatus",
    "ConnectionView",
    "ConnectorUses",
    "FlowCookie",
    "Handoff",
    "Installations",
    "NeedsReconnectError",
    "NotConnectedError",
    "Owner",
    "Problem",
    "ProviderAccess",
    "ProviderBusyError",
    "ProviderCall",
    "ProviderRefusedError",
    "ProviderResponse",
    "ProviderSession",
    "ProviderUnavailableError",
]


@dataclass(frozen=True, slots=True)
class ConnectionView:
    """One connection as a consumer sees it: its app, owner and state, without secrets."""

    id: UUID
    app: App
    capability: Capability
    owner: Owner
    # Человек, чей это грант; у установки пространства — администратор, который её сделал.
    user_id: UUID
    org_id: UUID | None
    status: ConnectionStatus
    problem: Problem | None
    # Адрес или имя аккаунта у провайдера — персональные данные дома, только для экранов.
    account_label: str | None
    # Несекретное: сайты Atlassian, команда Slack, тенант Microsoft.
    provider_meta: Mapping[str, object]
    connected_at: datetime

    @property
    def usable(self) -> bool:
        """Whether a consumer may call the provider through this connection now."""
        return self.status is ConnectionStatus.ACTIVE


class ConnectionRegistry(Protocol):
    """Reads of the registry, inside the caller's transaction and its row-level security."""

    async def of_person(
        self, session: AsyncSession, user_id: UUID, capability: Capability | None = None
    ) -> tuple[ConnectionView, ...]:
        """The person's own connections, of one capability or all."""
        ...

    async def of_workspace(
        self, session: AsyncSession, org_id: UUID, app: App
    ) -> tuple[ConnectionView, ...]:
        """A workspace's installations of one app."""
        ...

    async def get(self, session: AsyncSession, connection_id: UUID) -> ConnectionView | None:
        """One connection the scope may read, or None."""
        ...

    async def usable_for(self, session: AsyncSession, connection_id: UUID, org_id: UUID) -> bool:
        """Whether a person's connection may serve that workspace now (CN-D3).

        True while the connection is the workspace's own installation, or while its person is
        an active member of the workspace; a former member's Drive is never read for it.
        """
        ...


class ProviderAccess(Protocol):
    """Opens authorized sessions on connections; never inside a database transaction."""

    def open(self, home: Home, connection_id: UUID) -> AbstractAsyncContextManager[ProviderSession]:
        """A session on one connection of the home; `NotConnectedError` when there is none."""
        ...


@dataclass(frozen=True, slots=True)
class FlowCookie:
    """The browser-binding cookie of a connect flow, set by whichever route starts it."""

    name: str
    value: str
    path: str
    max_age_seconds: int

    def set_cookie_arguments(self) -> Mapping[str, object]:
        """The keyword arguments of `Response.set_cookie` for this cookie."""
        return {
            "key": self.name, "value": self.value, "path": self.path,
            "max_age": self.max_age_seconds, "httponly": True, "secure": True, "samesite": "lax",
        }  # fmt: skip


@dataclass(frozen=True, slots=True)
class Handoff:
    """A started connect flow: where the popup goes and the cookie that binds the browser."""

    authorize_url: str
    expires_at: datetime
    cookie: FlowCookie


class Installations(Protocol):
    """A workspace's installations of an app into a provider's tenant (chats' Slack)."""

    async def begin(
        self,
        session: AsyncSession,
        org_id: UUID,
        admin_user_id: UUID,
        app: App,
        *,
        reinstall_of: UUID | None = None,
    ) -> Handoff:
        """Start an installation by a workspace admin; the caller has checked the role."""
        ...

    async def remove(self, session: AsyncSession, org_id: UUID, connection_id: UUID) -> None:
        """Remove an installation; its grant is revoked after the caller's commit."""
        ...


@dataclass(frozen=True, slots=True)
class ConnectorUses:
    """The apps one consumer slice uses; the catalogue offers the union (CN-D4)."""

    consumer: str
    apps: frozenset[App]


class NotConnectedError(AppError):
    """The connection does not exist for the caller's scope."""

    def __init__(self) -> None:
        super().__init__("not_connected", HTTPStatus.NOT_FOUND)


class NeedsReconnectError(AppError):
    """The connection needs its person: the problem names what to repair."""

    def __init__(self, problem: Problem) -> None:
        super().__init__("needs_reconnect", HTTPStatus.CONFLICT, params={"problem": problem})
        self.problem = problem


CONNECTIONS: Final = PortKey[ConnectionRegistry]("connectors.connections")
PROVIDER_ACCESS: Final = PortKey[ProviderAccess]("connectors.provider_access")
INSTALLATIONS: Final = PortKey[Installations]("connectors.installations")
CONNECTOR_USES: Final = PortKey[ConnectorUses]("connectors.uses", Cardinality.MANY)
