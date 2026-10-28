"""Reading connections as consumers see them: the app, the owner, the state shown, no secret.

A connection's state is its grant's problem first, then its own (`shown_state`). Every read
runs in the caller's transaction, under its row-level security: a person's personal rows and
the rows of the workspaces the scope may read, nothing else.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement, Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.connectors.contracts import ConnectionView
from shosai.features.connectors.domain.catalogue import App, Owner, spec_of
from shosai.features.connectors.domain.states import (
    ConnectionState,
    ConnectionStatus,
    GrantState,
    GrantStatus,
    Problem,
    shown_state,
)
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord, GrantRecord


@dataclass(frozen=True, slots=True)
class ConnectionBinding:
    """A connection with what a provider session needs of its grant."""

    view: ConnectionView
    grant_id: UUID
    client_key: str


COLUMNS = (
    ConnectionRecord.id, ConnectionRecord.app, ConnectionRecord.user_id, ConnectionRecord.org_id,
    ConnectionRecord.status, ConnectionRecord.problem, ConnectionRecord.connected_at,
    ConnectionRecord.grant_id, GrantRecord.client_key, GrantRecord.status.label("grant_status"),
    GrantRecord.problem.label("grant_problem"), GrantRecord.account_label,
    GrantRecord.provider_meta,
)  # fmt: skip


def binding_of(row: Row[tuple[object, ...]]) -> ConnectionBinding:
    """A read row as a binding."""
    mapping = row._mapping
    app = App(str(mapping["app"]))
    own_problem = mapping["problem"]
    own = ConnectionState(
        ConnectionStatus(str(mapping["status"])),
        None if own_problem is None else Problem(str(own_problem)),
    )
    grant_status = GrantStatus(str(mapping["grant_status"]))
    grant_problem = mapping["grant_problem"]
    grant = GrantState(
        grant_status,
        None if grant_problem is None or grant_status is not GrantStatus.NEEDS_RECONNECT
        else Problem(str(grant_problem)),
    )  # fmt: skip
    shown = shown_state(grant, own)
    org_id = mapping["org_id"]
    view = ConnectionView(
        id=mapping["id"], app=app, capability=spec_of(app).capability,
        owner=Owner.PERSON if org_id is None else Owner.WORKSPACE, user_id=mapping["user_id"],
        org_id=org_id, status=shown.status, problem=shown.problem,
        account_label=mapping["account_label"], provider_meta=dict(mapping["provider_meta"] or {}),
        connected_at=mapping["connected_at"],
    )  # fmt: skip
    return ConnectionBinding(view, mapping["grant_id"], str(mapping["client_key"]))


async def bindings(
    session: AsyncSession, *conditions: ColumnElement[bool]
) -> Sequence[ConnectionBinding]:
    """The connections the conditions pick, with their grants, by app."""
    query = (
        select(*COLUMNS)
        .join(GrantRecord, GrantRecord.id == ConnectionRecord.grant_id)
        .where(*conditions)
        .order_by(ConnectionRecord.app, ConnectionRecord.id)
    )
    return [binding_of(row) for row in (await session.execute(query)).all()]


async def binding(session: AsyncSession, connection_id: UUID) -> ConnectionBinding | None:
    """One connection the scope may read, or None."""
    found = await bindings(session, ConnectionRecord.id == connection_id)
    return found[0] if found else None
