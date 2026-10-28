"""The due grants of a home: keep-alive refreshes and revocations (plan §3.5, CN-D11).

The sweep only reads, as the sweep role, across the home's people and workspaces; each
due grant becomes a task that claims it in its owner's own scope with a conditional update,
so a grant swept twice before its task runs is still worked once. The sweep role never
writes (ADR 0067).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import Select, func, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.domain.states import GrantStatus
from shosai.features.connectors.infrastructure.store.records import GrantRecord, GrantSecretRecord

SWEEP_LIMIT: Final = 200


@dataclass(frozen=True, slots=True)
class DueGrant:
    """A due grant and the scope its task runs in."""

    grant_id: UUID
    user_id: UUID
    org_id: UUID | None


class DueGrants:
    """Reads the due grants of a home."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    async def keepalive(self, home: Home) -> Sequence[DueGrant]:
        """Grants whose refresh token must be used before the provider forgets it."""
        secrets = GrantSecretRecord
        query = (
            select(secrets.grant_id, secrets.user_id, secrets.org_id)
            .where(secrets.keepalive_at.is_not(None), secrets.keepalive_at <= func.now())
            .order_by(secrets.keepalive_at, secrets.grant_id)
            .limit(SWEEP_LIMIT)
        )
        return await self._due(home, query)

    async def revocations(self, home: Home) -> Sequence[DueGrant]:
        """Grants left without an app, due for their provider's revocation."""
        query = (
            select(GrantRecord.id, GrantRecord.user_id, GrantRecord.org_id)
            .where(
                GrantRecord.status == GrantStatus.REVOKING.value,
                GrantRecord.revoke_at <= func.now(),
            )
            .order_by(GrantRecord.revoke_at, GrantRecord.id)
            .limit(SWEEP_LIMIT)
        )
        return await self._due(home, query)

    async def _due(self, home: Home, query: Select[UUID, UUID, UUID | None]) -> Sequence[DueGrant]:
        async with self._transactions.begin(TenancyScope(home), read_only=True, sweep=True) as s:
            rows = (await s.execute(query)).all()
        return [DueGrant(row[0], row[1], row[2]) for row in rows]
