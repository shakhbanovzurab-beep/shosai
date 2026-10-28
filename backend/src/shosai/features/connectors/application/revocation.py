"""Revoking a grant at its provider and forgetting it (plan §3.5).

A grant left without an app is `revoking` with its due time. The revocation task claims it by
moving that time a lease forward, asks the provider to revoke it — with the refresh token at
Google, the token elsewhere, the whole grant at GitHub; nothing where the provider has no
revocation — and deletes it with its secrets. A refusal tries again later, up to five times
with a growing pause; after the fifth the grant is forgotten anyway and counted, since keeping
a token Shosai no longer uses is worse than a revocation that never came. An account's
erasure revokes each of the person's grants once, at once.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

import httpx
import structlog
from pydantic import SecretStr
from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.crypto.key_ring import FernetKeyRing, UndecryptableCiphertextError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.domain.catalogue import Provider
from shosai.features.connectors.domain.states import GrantStatus
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.providers.base import (
    HeldTokens,
    ProviderRegistry,
    RevocationFailedError,
)
from shosai.features.connectors.infrastructure.store.records import (
    ConnectionRecord,
    GrantRecord,
    GrantSecretRecord,
)

CLAIM_LEASE: Final = timedelta(minutes=5)
ATTEMPTS: Final = 5
FIRST_PAUSE: Final = timedelta(minutes=2)
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RevokeTools:
    """What a revocation uses besides the database."""

    registry: ProviderRegistry
    http: httpx.AsyncClient
    keys: FernetKeyRing | None
    metrics: ConnectorsMetrics


@dataclass(frozen=True, slots=True)
class Claimed:
    """A revoking grant this task holds, with its tokens."""

    grant_id: UUID
    provider: Provider
    client_key: str
    failures: int
    tokens: HeldTokens


class GrantRevoker:
    """Revokes grants at their providers and forgets them."""

    def __init__(self, transactions: HomeTransactions, tools: RevokeTools) -> None:
        self._transactions = transactions
        self._tools = tools

    async def revoke_due(self, scope: TenancyScope, grant_id: UUID) -> None:
        """Revoke one due grant of the scope; a grant someone else holds or revived is left."""
        claimed = await self._claim(scope, grant_id)
        if claimed is None:
            return
        try:
            await self.at_provider(claimed)
        except RevocationFailedError:
            if claimed.failures + 1 < ATTEMPTS:
                await self._later(scope, claimed)
                return
            self._tools.metrics.revoke_failed(claimed.provider)
            log.warning("Грант забыт без отзыва у провайдера", provider=claimed.provider.value)
        await self._forget(scope, grant_id)

    async def revoke_all(self, scope: TenancyScope, grant_ids: Sequence[UUID]) -> None:
        """Revoke the grants once each, at once — an account's erasure does not wait."""
        for grant_id in grant_ids:
            held = await self._held(scope, grant_id)
            if held is None:
                continue
            try:
                await self.at_provider(held)
            except RevocationFailedError:
                self._tools.metrics.revoke_failed(held.provider)
                log.warning(
                    "Отзыв при удалении аккаунта не подтверждён", provider=held.provider.value
                )

    async def at_provider(self, claimed: Claimed) -> None:
        """Ask the provider to revoke the grant; nothing to do without its application."""
        client = self._tools.registry.client(claimed.client_key)
        if client is None:
            log.warning(
                "Приложение гранта не настроено: отзыв невозможен", client=claimed.client_key
            )
            raise RevocationFailedError
        await client.adapter.revoke(self._tools.http, client.credentials, claimed.tokens)

    async def _claim(self, scope: TenancyScope, grant_id: UUID) -> Claimed | None:
        statement = (
            update(GrantRecord)
            .where(
                GrantRecord.id == grant_id,
                GrantRecord.status == GrantStatus.REVOKING.value,
                GrantRecord.revoke_at <= func.now(),
            )
            .values(revoke_at=func.now() + CLAIM_LEASE)
            .returning(GrantRecord.id)
        )
        async with self._transactions.begin(scope) as session:
            if (await session.execute(statement)).first() is None:
                return None
        return await self._held(scope, grant_id)

    async def _held(self, scope: TenancyScope, grant_id: UUID) -> Claimed | None:
        query = select(
            GrantRecord.provider, GrantRecord.client_key, GrantRecord.consecutive_failures,
            GrantSecretRecord.access_token_enc, GrantSecretRecord.refresh_token_enc,
        ).outerjoin(GrantSecretRecord, GrantSecretRecord.grant_id == GrantRecord.id).where(
            GrantRecord.id == grant_id
        )  # fmt: skip
        async with self._transactions.begin(scope, read_only=True) as session:
            row = (await session.execute(query)).first()
        if row is None:
            return None
        tokens = HeldTokens(self._open(row.access_token_enc), self._open(row.refresh_token_enc))
        return Claimed(
            grant_id, Provider(row.provider), row.client_key, row.consecutive_failures, tokens
        )

    async def _later(self, scope: TenancyScope, claimed: Claimed) -> None:
        pause = FIRST_PAUSE * (2**claimed.failures)
        async with self._transactions.begin(scope) as session:
            await session.execute(
                update(GrantRecord)
                .where(GrantRecord.id == claimed.grant_id)
                .values(
                    consecutive_failures=GrantRecord.consecutive_failures + 1,
                    last_failure_at=func.now(),
                    revoke_at=func.now() + pause,
                )
            )

    async def _forget(self, scope: TenancyScope, grant_id: UUID) -> None:
        async with self._transactions.begin(scope) as session:
            await forget_orphan(session, grant_id)
        log.info("Грант отозван и забыт")

    def _open(self, ciphertext: bytes | None) -> SecretStr | None:
        keys = self._tools.keys
        if ciphertext is None or keys is None:
            return None
        try:
            return SecretStr(keys.decrypt(ciphertext))
        except UndecryptableCiphertextError:
            log.error("Секрет отзываемого гранта не расшифровывается")
            return None


async def forget_orphan(session: AsyncSession, grant_id: UUID) -> bool:
    """Delete a revoking grant with no app left, its secrets with it; whether it went."""
    statement = (
        delete(GrantRecord)
        .where(
            GrantRecord.id == grant_id,
            GrantRecord.status == GrantStatus.REVOKING.value,
            ~exists().where(ConnectionRecord.grant_id == grant_id),
        )
        .returning(GrantRecord.id)
    )
    return (await session.execute(statement)).first() is not None
