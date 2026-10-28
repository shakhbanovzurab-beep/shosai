"""The shapes of the cabinet's connectors routes (plan §3.7); names are global in OpenAPI.

A row keeps the cabinet's `connected` and `account` and adds the state, the problem to
repair and whether the provider would still list Shosai's access after a disconnect.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shosai.features.connectors.application.cabinet_list import ConnectorRow
from shosai.features.connectors.contracts.resources import MAX_PAGE, ResourcePage, ResourceQuery
from shosai.features.connectors.domain.catalogue import AuthKind
from shosai.features.connectors.domain.states import ConnectionStatus

type ConnectorAuth = Literal["oauth", "password", "api_key", "webhook"]
type ConnectorState = Literal["connected", "needs_reconnect", "not_connected"]
AUTHS: dict[AuthKind, ConnectorAuth] = {
    AuthKind.OAUTH2: "oauth", AuthKind.APP_LOGIN: "password", AuthKind.API_KEY: "api_key",
    AuthKind.WEBHOOK_URL: "webhook",
}  # fmt: skip


class ConnectorOut(BaseModel):
    """One app of Settings > Connectors and the person's connection of it."""

    id: str
    name: str
    category: str
    auth: ConnectorAuth
    connected: bool
    account: str | None
    status: ConnectorState
    problem: str | None
    connection_id: UUID | None
    connected_at: datetime | None
    # После отключения провайдер ещё покажет доступ Shosai: другие приложения гранта или нет отзыва.
    access_remains_at_provider: bool
    # Согласие живёт фиксированный срок (проект Google в Testing): переподключить до этого момента.
    reconnect_by: datetime | None


class ConnectorsOut(BaseModel):
    """The offered apps and the person's connections, in the catalogue's order."""

    items: list[ConnectorOut]


class ConnectorCredentialsIn(BaseModel):
    """A secret the person gives: exactly one of a password, a key or a hook URL."""

    model_config = ConfigDict(extra="forbid")

    login: str | None = Field(default=None, max_length=320)
    password: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, min_length=1, max_length=512)
    webhook_url: str | None = Field(default=None, min_length=1, max_length=2048)
    address: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def one_secret(self) -> ConnectorCredentialsIn:
        """Refuse no secret or two."""
        given = [value for value in (self.password, self.api_key, self.webhook_url) if value]
        if len(given) != 1:
            message = "нужен ровно один секрет: пароль, ключ или адрес хука"
            raise ValueError(message)
        return self

    @property
    def secret(self) -> str:
        """The one secret given."""
        return self.password or self.api_key or self.webhook_url or ""


class ConnectorResourcesQuery(BaseModel):
    """What a scope picker lists: a kind, under a parent or at the top, filtered, a page."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, max_length=32)
    parent: str | None = Field(default=None, max_length=512)
    q: str | None = Field(default=None, max_length=200)
    cursor: str | None = Field(default=None, max_length=1024)
    limit: int = Field(default=50, ge=1, le=MAX_PAGE)

    def query(self) -> ResourceQuery:
        """The browse this asks for."""
        return ResourceQuery(
            kind=self.kind, parent=self.parent, text=self.q, cursor=self.cursor, limit=self.limit
        )


class ConnectorResourceOut(BaseModel):
    """One place at the provider."""

    id: str
    name: str
    kind: str
    parent_id: str | None
    has_children: bool
    url: str | None


class ConnectorResourcesOut(BaseModel):
    """A page of places and the cursor of the next one."""

    items: list[ConnectorResourceOut]
    next_cursor: str | None


def connector_out(row: ConnectorRow) -> ConnectorOut:
    """A row as the cabinet reads it."""
    view = row.connection
    status: ConnectorState = "not_connected"
    if view is not None:
        status = "connected" if view.status is ConnectionStatus.ACTIVE else "needs_reconnect"
    return ConnectorOut(
        id=row.spec.app.value, name=row.spec.name, category=row.spec.category.value,
        auth=AUTHS[row.spec.auth[0]], connected=view is not None,
        account=None if view is None else view.account_label, status=status,
        problem=None if view is None or view.problem is None else view.problem.value,
        connection_id=None if view is None else view.id,
        connected_at=None if view is None else view.connected_at,
        access_remains_at_provider=row.access_remains_at_provider,
        reconnect_by=row.reconnect_by,
    )  # fmt: skip


def resources_out(page: ResourcePage) -> ConnectorResourcesOut:
    """A page as the cabinet reads it."""
    items = [
        ConnectorResourceOut(
            id=item.id, name=item.name, kind=item.kind, parent_id=item.parent_id,
            has_children=item.has_children, url=item.url,
        )
        for item in page.items
    ]  # fmt: skip
    return ConnectorResourcesOut(items=items, next_cursor=page.next_cursor)
