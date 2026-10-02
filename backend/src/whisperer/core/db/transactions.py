"""Short transactions in the home of a tenancy scope (target architecture §4.1, §7, §14 rule 1).

`begin(scope)` opens a session on the scope's home and starts a transaction whose first
statement sets, for this transaction only, the statement timeout of the process role,
read-only mode and the `app.user_id` and `app.org_id` that row-level security reads.
`SET LOCAL` dies with the transaction, so nothing reaches the next client of the same
server connection behind PgBouncer. The block commits on exit and rolls back on error.

There is no request-wide session: a handler commits before it answers and calls external
services between transactions, never inside one. Round trips per transaction: `BEGIN`,
the scope, one per statement, `COMMIT`: four of 45 ms for one read in the Russian home (§3).

The session remembers the scope and the mode of its transaction (`transaction_info`), so
work written into the caller's transaction — an outbox event — takes the transaction's
own tenancy instead of a second copy the caller could get wrong.
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Final

import structlog
from sqlalchemy import exc, text
from sqlalchemy.ext.asyncio import AsyncSession

from whisperer.core.db.engines import HomeDatabases
from whisperer.core.db.errors import HomeUnavailableError, connection_failure
from whisperer.core.db.home_checks import HomeGate
from whisperer.core.db.metrics import DatabaseMetrics, UnavailableReason
from whisperer.core.kernel.homes import Home
from whisperer.core.kernel.tenancy import TenancyScope

# Один оператор — один обмен с сервером; пустая строка означает «нет» для app_*_id().
SCOPE_STATEMENT: Final = text(
    "SELECT set_config('statement_timeout', :statement_timeout, true), "
    "set_config('transaction_read_only', :read_only, true), "
    "set_config('app.user_id', :user_id, true), "
    "set_config('app.org_id', :org_id, true)"
)
TRANSACTION_INFO_KEY: Final = "whisperer.transaction"
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TransactionInfo:
    """The tenancy scope and the mode of the transaction a session is in."""

    scope: TenancyScope
    read_only: bool


class NotAHomeTransactionError(Exception):
    """The session was not opened by `HomeTransactions.begin`: its scope is unknown."""


def transaction_info(session: AsyncSession) -> TransactionInfo:
    """The scope and mode of the session's transaction, as `HomeTransactions.begin` opened it."""
    info = session.info.get(TRANSACTION_INFO_KEY)
    if not isinstance(info, TransactionInfo):
        message = "сессия открыта не через HomeTransactions.begin: скоуп транзакции неизвестен"
        raise NotAHomeTransactionError(message)
    return info


class HomeTransactions:
    """Opens transactions in the home of a scope; slices receive it by injection."""

    def __init__(self, databases: HomeDatabases, gate: HomeGate, metrics: DatabaseMetrics) -> None:
        self._databases = databases
        self._gate = gate
        self._metrics = metrics
        timeout_ms = int(databases.profile.statement_timeout.total_seconds() * 1000)
        self._statement_timeout = str(timeout_ms)

    @asynccontextmanager
    async def begin(
        self, scope: TenancyScope, *, read_only: bool = False
    ) -> AsyncIterator[AsyncSession]:
        """A session in a transaction of the scope's home; commit on exit, rollback on error."""
        await self._gate.ensure_open(scope.home)
        factory = self._databases.sessions(scope.home)
        async with factory() as session, session.begin():
            await self._acquire(session, scope.home)
            await session.execute(SCOPE_STATEMENT, self._scope_values(scope, read_only=read_only))
            session.info[TRANSACTION_INFO_KEY] = TransactionInfo(scope, read_only=read_only)
            yield session

    async def _acquire(self, session: AsyncSession, home: Home) -> None:
        """Take a pooled connection; a home out of reach becomes 503, not a stuck request."""
        try:
            # Соединение нужно только взять из пула; сам объект сессия хранит у себя.
            _connection = await session.connection()
        except exc.TimeoutError as error:
            self._refuse(home, "pool_timeout", error)
            raise HomeUnavailableError(home) from error
        except exc.OperationalError as error:
            self._refuse(home, "connect_failed", error)
            raise HomeUnavailableError(home) from error

    def _refuse(self, home: Home, reason: UnavailableReason, error: exc.SQLAlchemyError) -> None:
        self._metrics.count_unavailable(home, reason)
        log.warning(
            "База дома не дала соединение",
            home=home.value,
            reason=reason,
            failure=connection_failure(error),
        )

    def _scope_values(self, scope: TenancyScope, *, read_only: bool) -> Mapping[str, str]:
        return {
            "statement_timeout": self._statement_timeout,
            "read_only": "on" if read_only else "off",
            "user_id": "" if scope.user_id is None else str(scope.user_id),
            "org_id": "" if scope.org_id is None else str(scope.org_id),
        }
