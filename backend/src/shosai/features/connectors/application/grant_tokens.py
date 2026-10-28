"""A grant's live access token: one refresh at a time, a rotated token never lost (§3.5).

The secrets are read once. A token that expires within two minutes — or the one a caller saw
refused with a 401 — is refreshed by whoever takes the lease: a conditional update on the
grant's generation that holds for 30 seconds. The winner calls the token endpoint outside
any transaction and writes the new tokens on the same generation, so a race writes once and
a rotating refresh token is stored by the one who received it. A loser waits up to three
seconds for the generation to move. A refused grant breaks for all its apps; a refusal of
Shosai's own application is an alert and breaks nothing; anything else is transient.
"""

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import httpx
import structlog
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.crypto.key_ring import FernetKeyRing, UndecryptableCiphertextError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.health import break_grant, count_failure
from shosai.features.connectors.contracts import NeedsReconnectError, ProviderBusyError
from shosai.features.connectors.contracts.provider import ProviderUnavailableError
from shosai.features.connectors.domain.catalogue import Provider
from shosai.features.connectors.domain.refresh import RefreshOutcome, keepalive_at, needs_refresh
from shosai.features.connectors.domain.states import GrantStatus, Problem
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.oauth.tokens import (
    TokenEndpoint,
    TokenEndpointError,
    TokenSet,
)
from shosai.features.connectors.infrastructure.providers.base import (
    ConfiguredClient,
    ProviderRegistry,
)
from shosai.features.connectors.infrastructure.store.records import GrantRecord, GrantSecretRecord

LEASE: Final = timedelta(seconds=30)
WAIT: Final = timedelta(seconds=3)
POLL: Final = timedelta(milliseconds=200)
WRITE_ATTEMPTS: Final = 3
KEEPALIVE_RETRY: Final = timedelta(hours=1)
# Сбои записи, после которых повтор внутри аренды имеет смысл: база или связь с ней.
WRITE_FAILURES: Final = (SQLAlchemyError, OSError, TimeoutError)
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HeldGrant:
    """A grant's state and secrets as one read saw them."""

    grant_id: UUID
    status: GrantStatus
    problem: Problem | None
    provider: Provider
    client_key: str
    access_token_enc: bytes | None
    refresh_token_enc: bytes | None
    expires_at: datetime | None
    generation: int


@dataclass(frozen=True, slots=True)
class TokenTools:
    """What refreshing uses besides the database."""

    registry: ProviderRegistry
    http: httpx.AsyncClient
    # Без кольца ключей гранты не читаются и не пишутся: вызовы отвечают «недоступно».
    keys: FernetKeyRing | None
    outbox: EventOutbox
    metrics: ConnectorsMetrics


class GrantTokens:
    """The access tokens of grants, refreshed when they must be."""

    def __init__(
        self,
        transactions: HomeTransactions,
        tools: TokenTools,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._transactions = transactions
        self._tools = tools
        self._clock = clock
        self._sleep = sleep

    async def access(
        self, scope: TenancyScope, grant_id: UUID, *, refused: SecretStr | None = None
    ) -> SecretStr:
        """The grant's live access token; `refused` is one the provider just answered 401 to."""
        held = await self.read(scope, grant_id)
        current = self._decrypt(held.access_token_enc)
        stale = (
            refused is not None
            and current is not None
            and (current.get_secret_value() == refused.get_secret_value())
        )
        if current is not None and not stale and not needs_refresh(held.expires_at, self._clock()):
            return current
        return await self.refresh(scope, held)

    async def keep_alive(self, scope: TenancyScope, grant_id: UUID) -> None:
        """Refresh a grant whose refresh token would die unused; a failure waits an hour."""
        claim = (
            update(GrantSecretRecord)
            .where(
                GrantSecretRecord.grant_id == grant_id,
                GrantSecretRecord.keepalive_at <= func.now(),
            )
            .values(keepalive_at=func.now() + KEEPALIVE_RETRY)
            .returning(GrantSecretRecord.grant_id)
        )
        async with self._transactions.begin(scope) as session:
            if (await session.execute(claim)).first() is None:
                return
        try:
            await self.refresh(scope, await self.read(scope, grant_id))
        except (NeedsReconnectError, ProviderUnavailableError, ProviderBusyError) as error:
            # Состояние гранта уже записано обновлением; следующий заход — через час.
            log.info("Keep-alive гранта не удался", error=type(error).__name__)

    async def revoked_at_provider(self, scope: TenancyScope, grant_id: UUID) -> None:
        """A fresh token was refused: the grant is gone at the provider (`grant_revoked`)."""
        async with self._transactions.begin(scope) as session:
            await break_grant(session, self._tools.outbox, grant_id, Problem.GRANT_REVOKED)

    async def read(self, scope: TenancyScope, grant_id: UUID) -> HeldGrant:
        """The grant and its secrets; `NeedsReconnectError` when the grant does not work."""
        query = select(
            GrantRecord.status, GrantRecord.problem, GrantRecord.provider, GrantRecord.client_key,
            GrantSecretRecord.access_token_enc, GrantSecretRecord.refresh_token_enc,
            GrantSecretRecord.expires_at, GrantSecretRecord.refresh_generation,
        ).join(GrantSecretRecord, GrantSecretRecord.grant_id == GrantRecord.id).where(
            GrantRecord.id == grant_id
        )  # fmt: skip
        async with self._transactions.begin(scope, read_only=True) as session:
            row = (await session.execute(query)).first()
        if row is None:
            raise NeedsReconnectError(Problem.GRANT_REVOKED)
        status = GrantStatus(row.status)
        if status is not GrantStatus.ACTIVE:
            raise NeedsReconnectError(
                Problem(row.problem) if row.problem else Problem.GRANT_REVOKED
            )
        return HeldGrant(
            grant_id, status, None, Provider(row.provider), row.client_key, row.access_token_enc,
            row.refresh_token_enc, row.expires_at, row.refresh_generation,
        )  # fmt: skip

    async def refresh(self, scope: TenancyScope, held: HeldGrant) -> SecretStr:
        """A new access token under the lease, or the one the lease's holder wrote."""
        refresh = self._decrypt(held.refresh_token_enc)
        client = self._tools.registry.client(held.client_key)
        if refresh is None or client is None:
            if refresh is None:
                await self._break(scope, held, Problem.GRANT_REVOKED)
                raise NeedsReconnectError(Problem.GRANT_REVOKED)
            raise ProviderUnavailableError
        if not await self._lease(scope, held):
            return await self._wait(scope, held)
        tokens = await self._call(scope, held, client, refresh)
        await self._store(scope, held, client, tokens)
        return tokens.access_token

    async def _call(
        self, scope: TenancyScope, held: HeldGrant, client: ConfiguredClient, refresh: SecretStr
    ) -> TokenSet:
        endpoint = TokenEndpoint(self._tools.http, client.adapter.descriptor, client.credentials)
        try:
            payload = await endpoint.refresh(refresh)
            tokens = client.adapter.tokens(payload, self._clock())
        except TokenEndpointError as error:
            await self._failed(scope, held, error.outcome)
            raise ProviderUnavailableError from None
        self._tools.metrics.refreshed(held.provider, RefreshOutcome.REFRESHED)
        return tokens

    async def _failed(self, scope: TenancyScope, held: HeldGrant, outcome: RefreshOutcome) -> None:
        self._tools.metrics.refreshed(held.provider, outcome)
        if outcome is RefreshOutcome.GRANT_REFUSED:
            await self._break(scope, held, Problem.REFRESH_REFUSED)
            raise NeedsReconnectError(Problem.REFRESH_REFUSED)
        if outcome is RefreshOutcome.CLIENT_MISCONFIGURED:
            # Отказ нашему приложению: секрет истёк или отозван — тревога, гранты не трогаются.
            self._tools.metrics.client_misconfigured(held.client_key)
            log.error("Провайдер отверг приложение Shosai", client=held.client_key)
        async with self._transactions.begin(scope) as session:
            await count_failure(session, held.grant_id)
            await self._release(session, held)

    async def _break(self, scope: TenancyScope, held: HeldGrant, problem: Problem) -> None:
        async with self._transactions.begin(scope) as session:
            await break_grant(session, self._tools.outbox, held.grant_id, problem)
            await self._release(session, held)

    async def _lease(self, scope: TenancyScope, held: HeldGrant) -> bool:
        statement = (
            update(GrantSecretRecord)
            .where(
                GrantSecretRecord.grant_id == held.grant_id,
                GrantSecretRecord.refresh_generation == held.generation,
                (GrantSecretRecord.refreshing_until.is_(None))
                | (GrantSecretRecord.refreshing_until < func.now()),
            )
            .values(refreshing_until=func.now() + LEASE)
            .returning(GrantSecretRecord.grant_id)
        )
        async with self._transactions.begin(scope) as session:
            return (await session.execute(statement)).first() is not None

    async def _release(self, session: AsyncSession, held: HeldGrant) -> None:
        release = (
            update(GrantSecretRecord)
            .where(
                GrantSecretRecord.grant_id == held.grant_id,
                GrantSecretRecord.refresh_generation == held.generation,
            )
            .values(refreshing_until=None)
        )
        await session.execute(release)

    async def _store(
        self, scope: TenancyScope, held: HeldGrant, client: ConfiguredClient, tokens: TokenSet
    ) -> None:
        keys, now = self._tools.keys, self._clock()
        if keys is None:
            raise ProviderUnavailableError
        values: dict[str, object] = {
            "access_token_enc": keys.encrypt(tokens.access_token.get_secret_value()),
            "expires_at": tokens.expires_at, "refresh_generation": held.generation + 1,
            "refreshing_until": None, "refreshed_at": func.now(),
            "keepalive_at": keepalive_at(
                now, client.adapter.descriptor.idle_expiry, secrets.SystemRandom().uniform(-1, 1)
            ),
        }  # fmt: skip
        if tokens.refresh_token is not None:
            values["refresh_token_enc"] = keys.encrypt(tokens.refresh_token.get_secret_value())
        write = (
            update(GrantSecretRecord)
            .where(
                GrantSecretRecord.grant_id == held.grant_id,
                GrantSecretRecord.refresh_generation == held.generation,
            )
            .values(values)
        )
        for attempt in range(1, WRITE_ATTEMPTS + 1):
            try:
                async with self._transactions.begin(scope) as session:
                    await session.execute(write)
                return
            except WRITE_FAILURES as error:
                log.warning("Новые токены не записаны", attempt=attempt, error=type(error).__name__)
        self._tools.metrics.refresh_lost()
        log.error("Повёрнутый токен потерян: грант ждёт человека при следующем вызове")
        raise ProviderUnavailableError

    async def _wait(self, scope: TenancyScope, held: HeldGrant) -> SecretStr:
        deadline = self._clock() + WAIT
        while self._clock() < deadline:
            await self._sleep(POLL.total_seconds())
            again = await self.read(scope, held.grant_id)
            if again.generation > held.generation:
                token = self._decrypt(again.access_token_enc)
                if token is not None:
                    return token
        raise ProviderBusyError(1)

    def _decrypt(self, ciphertext: bytes | None) -> SecretStr | None:
        if ciphertext is None or self._tools.keys is None:
            return None
        try:
            return SecretStr(self._tools.keys.decrypt(ciphertext))
        except UndecryptableCiphertextError:
            log.error("Секрет гранта не расшифровывается ни одним ключом кольца")
            return None
