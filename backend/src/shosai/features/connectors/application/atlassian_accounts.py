"""Atlassian's personal data report for one home (plan §3.5, CN-D9).

Every Atlassian grant of the home is reported with the moment its profile was read, through
the token of a person whose grant works — the report API takes any person of the app's. A
closed account's grant is erased with its apps (`provider_closed`), as nothing may stay of
it. A changed account's profile and sites are read again. The sweep role only reads, and every
write runs in the grant owner's scope.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

import httpx
import structlog
from sqlalchemy import delete, select, update

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.grant_tokens import GrantTokens
from shosai.features.connectors.contracts import NeedsReconnectError
from shosai.features.connectors.contracts.events import ConnectionRevoked, RevokeReason
from shosai.features.connectors.contracts.provider import (
    ProviderBusyError,
    ProviderUnavailableError,
)
from shosai.features.connectors.domain.account_report import (
    DEFAULT_CYCLE,
    ReportedAccount,
    Verdict,
    accounts_of,
    batches,
)
from shosai.features.connectors.domain.catalogue import App, Provider
from shosai.features.connectors.domain.states import GrantStatus
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.providers.atlassian import read_profile
from shosai.features.connectors.infrastructure.providers.atlassian_report import (
    ReportAnswer,
    ReportTokenRefusedError,
    report_accounts,
)
from shosai.features.connectors.infrastructure.providers.base import ProviderAnswerError
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord, GrantRecord

log = structlog.stdlib.get_logger(__name__)

# Сколько разных людей пробуется ради токена одной партии, прежде чем отчёт отложен.
TOKEN_ATTEMPTS: Final = 5
UNREADY: Final = (NeedsReconnectError, ProviderBusyError, ProviderUnavailableError)


@dataclass(frozen=True, slots=True)
class HeldAccount:
    """One Atlassian grant of the home, as the report reads it."""

    grant_id: UUID
    user_id: UUID
    org_id: UUID | None
    account_id: str
    profile_at: datetime
    active: bool

    def scope(self, home: Home) -> TenancyScope:
        """The grant owner's scope."""
        return TenancyScope(home, self.user_id, self.org_id)


@dataclass(frozen=True, slots=True)
class ReportTools:
    """What the report uses besides the database."""

    tokens: GrantTokens
    http: httpx.AsyncClient
    outbox: EventOutbox
    metrics: ConnectorsMetrics


def profile_moment(meta: object, created_at: datetime) -> datetime:
    """When the grant's profile was read: `profile_at` of its meta, else when it was made."""
    value = meta.get("profile_at") if isinstance(meta, dict) else None
    try:
        return datetime.fromisoformat(value) if isinstance(value, str) else created_at
    except ValueError:
        return created_at


class AtlassianAccounts:
    """Reports a home's Atlassian accounts and acts on Atlassian's verdicts."""

    def __init__(self, transactions: HomeTransactions, tools: ReportTools) -> None:
        self._transactions = transactions
        self._tools = tools

    async def report(self, home: Home) -> None:
        """One cycle's report of the home; transient failures leave it for the task's retry."""
        held = await self._held(home)
        if not held:
            return
        accounts = accounts_of([ReportedAccount(h.account_id, h.profile_at) for h in held])
        reporters = [account for account in held if account.active]
        verdicts: dict[str, Verdict] = {}
        for batch in batches(accounts):
            answer = await self._report(home, batch, reporters)
            verdicts |= answer.verdicts
            if answer.cycle is not None and answer.cycle < DEFAULT_CYCLE:
                log.warning("Atlassian назначил цикл отчёта короче недели", days=answer.cycle.days)
        for account in held:
            verdict = verdicts.get(account.account_id)
            if verdict is Verdict.CLOSED:
                await self.close(account.scope(home), account.grant_id)
            elif verdict is Verdict.UPDATED:
                await self.reread(account.scope(home), account.grant_id)
        self._tools.metrics.reported(Provider.ATLASSIAN, len(accounts), verdicts.values())

    async def close(self, scope: TenancyScope, grant_id: UUID) -> None:
        """Erase the grant of a closed account with its apps."""
        removed = (
            delete(ConnectionRecord)
            .where(ConnectionRecord.grant_id == grant_id)
            .returning(ConnectionRecord.id, ConnectionRecord.user_id, ConnectionRecord.app)
        )
        async with self._transactions.begin(scope) as session:
            gone = (await session.execute(removed)).all()
            await session.execute(delete(GrantRecord).where(GrantRecord.id == grant_id))
            await self._tools.outbox.add_all(session, [
                ConnectionRevoked(
                    connection_id=row.id, user_id=row.user_id, org_id=scope.org_id,
                    app=App(row.app), reason=RevokeReason.PROVIDER_CLOSED,
                )
                for row in gone
            ])  # fmt: skip
        log.info("Грант закрытого аккаунта Atlassian стёрт", apps=len(gone))

    async def reread(self, scope: TenancyScope, grant_id: UUID) -> None:
        """Read a changed account's profile and sites again; a grant that does not work waits."""
        try:
            token = await self._tools.tokens.access(scope, grant_id)
            identity = await read_profile(self._tools.http, token.get_secret_value())
        except (*UNREADY, ProviderAnswerError, httpx.HTTPError) as error:
            log.info("Профиль Atlassian не перечитан", error=type(error).__name__)
            return
        refreshed = (
            update(GrantRecord)
            .where(
                GrantRecord.id == grant_id,
                GrantRecord.external_account_id == identity.external_account_id,
            )
            .values(account_label=identity.label, provider_meta=dict(identity.meta))
        )
        async with self._transactions.begin(scope) as session:
            await session.execute(refreshed)

    async def _report(
        self, home: Home, batch: Sequence[ReportedAccount], reporters: Sequence[HeldAccount]
    ) -> ReportAnswer:
        for reporter in reporters[:TOKEN_ATTEMPTS]:
            try:
                token = await self._tools.tokens.access(reporter.scope(home), reporter.grant_id)
                return await report_accounts(self._tools.http, token, batch)
            except NeedsReconnectError, ReportTokenRefusedError:
                continue
        log.error("Отчёт Atlassian не отправлен: нет токена, который он принял", home=home.value)
        raise ProviderUnavailableError

    async def _held(self, home: Home) -> list[HeldAccount]:
        grants = GrantRecord
        query = (
            select(
                grants.id, grants.user_id, grants.org_id, grants.external_account_id,
                grants.provider_meta, grants.created_at, grants.status,
            )
            .where(
                grants.provider == Provider.ATLASSIAN.value,
                grants.status != GrantStatus.REVOKING.value,
            )
            .order_by(grants.id)
        )  # fmt: skip
        async with self._transactions.begin(TenancyScope(home), read_only=True, sweep=True) as s:
            rows = (await s.execute(query)).all()
        return [
            HeldAccount(
                row.id, row.user_id, row.org_id, row.external_account_id,
                profile_moment(row.provider_meta, row.created_at),
                row.status == GrantStatus.ACTIVE.value,
            )
            for row in rows
        ]  # fmt: skip
