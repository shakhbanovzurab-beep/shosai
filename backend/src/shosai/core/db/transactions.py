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

import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Final

import structlog
from sqlalchemy import exc, text
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.database_roles import SWEEPER_ROLE
from shosai.core.db.engines import HomeDatabases
from shosai.core.db.errors import HomeUnavailableError, connection_failure
from shosai.core.db.home_checks import HomeGate
from shosai.core.db.metrics import DatabaseMetrics, UnavailableReason
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.observability.log_context import id_fields

# Один оператор — один обмен с сервером; пустая строка означает «нет» для app_*_id().
SCOPE_SETTINGS: Final = (
    "SELECT set_config('statement_timeout', :statement_timeout, true), "
    "set_config('transaction_read_only', :read_only, true), "
    "set_config('app.user_id', :user_id, true), "
    "set_config('app.org_id', :org_id, true)"
)
SCOPE_STATEMENT: Final = text(SCOPE_SETTINGS)
# Обход (ADR 0053 п. 2): та же команда переключает роль до конца транзакции — без лишнего обмена.
SWEEP_SCOPE_STATEMENT: Final = text(f"{SCOPE_SETTINGS}, set_config('role', :role, true)")
TRANSACTION_INFO_KEY: Final = "shosai.transaction"
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TransactionInfo:
    """The tenancy scope and the mode of the transaction a session is in."""

    scope: TenancyScope
    read_only: bool


class SweepNotAllowedError(Exception):
    """A sweep transaction was asked for in a process role whose profile does not allow it."""


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
        self, scope: TenancyScope, *, read_only: bool = False, sweep: bool = False
    ) -> AsyncIterator[AsyncSession]:
        """A session in a transaction of the scope's home; commit on exit, rollback on error.

        `sweep` runs the transaction as the sweep role, which row-level security lets see
        every tenant's rows (ADR 0053 point 2); only the workers' and the scheduler's
        profiles allow it, so a request handler can never open one.
        """
        if sweep and not self._databases.profile.sweeps:
            message = "обход по всем тенантам разрешён только воркерам и планировщику"
            raise SweepNotAllowedError(message)
        await self._gate.ensure_open(scope.home)
        factory = self._databases.sessions(scope.home)
        started = time.perf_counter()
        async with factory() as session, session.begin():
            await self._acquire(session, scope.home)
            values = self._scope_values(scope, read_only=read_only)
            if sweep:
                await session.execute(SWEEP_SCOPE_STATEMENT, {**values, "role": SWEEPER_ROLE})
            else:
                await session.execute(SCOPE_STATEMENT, values)
            session.info[TRANSACTION_INFO_KEY] = TransactionInfo(scope, read_only=read_only)
            yield session
        log.debug(
            "Транзакция зафиксирована", home=scope.home.value, read_only=read_only, sweep=sweep,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            **id_fields(user_id=scope.user_id, org_id=scope.org_id),
        )  # fmt: skip

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
