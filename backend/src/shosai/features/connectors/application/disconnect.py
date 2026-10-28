"""A person disconnecting an app (plan §3.5): every use of it stops at once.

The connection goes and `connectors.connection.revoked` is written in one transaction, so
every consumer stops in the same moment. The grant is revoked at the provider only when its
last app is gone; until then — and wherever the provider has no revocation for applications
— the provider still lists Shosai's access, which the cabinet says.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.contracts import NotConnectedError
from shosai.features.connectors.contracts.events import ConnectionRevoked, RevokeReason
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.domain.descriptors import RevocationKind
from shosai.features.connectors.infrastructure.providers.base import ProviderRegistry
from shosai.features.connectors.infrastructure.store.grant_writes import retire_if_orphaned
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord, GrantRecord


@dataclass(frozen=True, slots=True)
class Disconnected:
    """What a disconnect left behind."""

    connection_id: UUID
    # Провайдер ещё показывает доступ Shosai: другие приложения гранта или нет отзыва.
    access_remains_at_provider: bool


class Disconnector:
    """Disconnects a person's apps."""

    def __init__(
        self, transactions: HomeTransactions, outbox: EventOutbox, registry: ProviderRegistry
    ) -> None:
        self._transactions = transactions
        self._outbox = outbox
        self._registry = registry

    async def disconnect(self, scope: TenancyScope, app: App) -> Disconnected:
        """End the person's connection of the app; `NotConnectedError` when there is none."""
        if scope.user_id is None:
            raise NotConnectedError
        statement = (
            delete(ConnectionRecord)
            .where(
                ConnectionRecord.user_id == scope.user_id,
                ConnectionRecord.org_id.is_(None),
                ConnectionRecord.app == app.value,
            )
            .returning(ConnectionRecord.id, ConnectionRecord.grant_id)
        )
        async with self._transactions.begin(scope) as session:
            removed = (await session.execute(statement)).first()
            if removed is None:
                raise NotConnectedError
            orphaned = await retire_if_orphaned(session, removed.grant_id)
            client_key = await session.scalar(
                select(GrantRecord.client_key).where(GrantRecord.id == removed.grant_id)
            )
            await self._outbox.add(
                session,
                ConnectionRevoked(
                    connection_id=removed.id, user_id=scope.user_id, app=app,
                    reason=RevokeReason.DISCONNECTED,
                ),
            )  # fmt: skip
        client = self._registry.client(client_key or "")
        revocable = client is not None and (
            client.adapter.descriptor.revocation.kind is not RevocationKind.NONE
        )
        return Disconnected(removed.id, access_remains_at_provider=not (orphaned and revocable))
