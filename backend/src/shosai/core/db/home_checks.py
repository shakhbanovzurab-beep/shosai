"""Whether a home's database is that home and its schema fits this code (ADR 0010).

At start every home is checked. A database of another home, or one whose schema is behind
the code, stops the start: the addresses are swapped or the release skipped a migration.
A schema newer than the code passes: a later release migrated it, and migrations only
expand the schema, so the previous image can be rolled back to (§17, F1-D7). A home out
of reach does not stop the start (§13.2, F1-D8): its transactions are refused with 503,
and the check is repeated before its first transaction once it may have come back.
"""

import asyncio
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

import structlog
from sqlalchemy import exc, text
from sqlalchemy.ext.asyncio import AsyncEngine

from shosai.core.config.sections import home_prefix
from shosai.core.db.engines import HomeDatabases
from shosai.core.db.errors import RETRY_AFTER_SECONDS, HomeUnavailableError, connection_failure
from shosai.core.db.metrics import DatabaseMetrics
from shosai.core.db.migrations import MigrationHistory, RevisionState
from shosai.core.kernel.homes import Home

IDENTITY_STATEMENT: Final = text(
    "SELECT (SELECT home FROM home_identity) AS home, "
    "(SELECT version_num FROM alembic_version) AS revision"
)
UNDEFINED_TABLE: Final = "42P01"
log = structlog.stdlib.get_logger(__name__)


class HomeState(StrEnum):
    """Where the check of one home's database stands."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    UNREACHABLE = "unreachable"
    WRONG_HOME = "wrong_home"
    BEHIND = "behind"


FATAL_STATES: Final = frozenset({HomeState.WRONG_HOME, HomeState.BEHIND})
RETRIED_STATES: Final = frozenset({HomeState.UNVERIFIED, HomeState.UNREACHABLE})


@dataclass(frozen=True, slots=True)
class HomeCheck:
    """What the check of one home found."""

    home: Home
    state: HomeState
    found_home: str | None = None
    revision: str | None = None
    failure: str | None = None

    def describe(self) -> str:
        """One line for the start log, naming the variable of the address."""
        variable = f"{home_prefix(self.home)}DATABASE_URL"
        match self.state:
            case HomeState.VERIFIED:
                return f"{variable}: дом {self.home}, ревизия {self.revision}"
            case HomeState.UNVERIFIED:
                return f"{variable}: база дома {self.home} ещё не проверена"
            case HomeState.UNREACHABLE:
                return f"{variable}: база дома {self.home} недоступна: {self.failure}"
            case HomeState.WRONG_HOME:
                return f"{variable}: ведёт в базу дома {self.found_home}, а не {self.home}"
            case HomeState.BEHIND:
                found = self.revision or "нет ревизии"
                return f"{variable}: схема отстаёт от кода ({found}); нужна `shosai migrate`"


class HomeMisconfiguredError(Exception):
    """A home's database is another home's or behind the code; the process must not start."""

    def __init__(self, checks: Sequence[HomeCheck]) -> None:
        self.checks = tuple(checks)
        lines = [check.describe() for check in checks]
        super().__init__("Базы домов не подходят процессу:\n" + "\n".join(lines))


async def check_home(engine: AsyncEngine, home: Home, history: MigrationHistory) -> HomeCheck:
    """Read the home identity and the revision through the application's own pool."""
    try:
        async with engine.connect() as connection:
            row = (await connection.execute(IDENTITY_STATEMENT)).one()
    except exc.ProgrammingError as error:
        if getattr(error.orig, "sqlstate", None) != UNDEFINED_TABLE:
            raise
        return HomeCheck(home, HomeState.BEHIND)
    except (exc.OperationalError, exc.TimeoutError) as error:
        return HomeCheck(home, HomeState.UNREACHABLE, failure=connection_failure(error))
    found_home, revision = row.home, row.revision
    if found_home != home.value:
        return HomeCheck(home, HomeState.WRONG_HOME, found_home=found_home, revision=revision)
    revision_state = history.state_of(revision)
    if revision_state is RevisionState.BEHIND:
        return HomeCheck(home, HomeState.BEHIND, found_home=found_home, revision=revision)
    if revision_state is RevisionState.NEWER:
        log.warning(
            "Схема дома новее кода: работает предыдущий образ", home=home.value, revision=revision
        )
    return HomeCheck(home, HomeState.VERIFIED, found_home=found_home, revision=revision)


class HomeGate:
    """Lets transactions into a home only after its database has been verified."""

    def __init__(
        self,
        databases: HomeDatabases,
        history: MigrationHistory,
        metrics: DatabaseMetrics,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._databases = databases
        self._history = history
        self._metrics = metrics
        self._clock = clock
        self._states = dict.fromkeys(Home, HomeState.UNVERIFIED)
        self._next_attempt = dict.fromkeys(Home, 0.0)
        self._locks = {home: asyncio.Lock() for home in Home}

    async def verify_at_start(self) -> tuple[HomeCheck, ...]:
        """Check every home at once; raise if any is another home's or behind the code."""
        checks = tuple(await asyncio.gather(*(self._check(home) for home in Home)))
        fatal = [check for check in checks if check.state in FATAL_STATES]
        if fatal:
            raise HomeMisconfiguredError(fatal)
        return checks

    def is_closed(self, home: Home) -> bool:
        """Whether the check found another home's database or a schema behind the code."""
        return self._states[home] in FATAL_STATES

    async def ensure_open(self, home: Home) -> None:
        """Return for a verified home; otherwise check it again or refuse with 503."""
        if self._states[home] is HomeState.VERIFIED:
            return
        async with self._locks[home]:
            state = self._states[home]
            if state is HomeState.VERIFIED:
                return
            if state in RETRIED_STATES and self._clock() >= self._next_attempt[home]:
                state = (await self._check(home)).state
            if state is not HomeState.VERIFIED:
                self._metrics.count_unavailable(home, "unverified")
                raise HomeUnavailableError(home)

    async def _check(self, home: Home) -> HomeCheck:
        check = await check_home(self._databases.engine(home), home, self._history)
        self._states[home] = check.state
        self._metrics.record_home_state(home, check.state.value)
        if check.state is HomeState.UNREACHABLE:
            self._next_attempt[home] = self._clock() + RETRY_AFTER_SECONDS
            log.warning(
                "База дома не проверена: недоступна", home=home.value, failure=check.failure
            )
        elif check.state in FATAL_STATES:
            # Дом закрыт до перезапуска: в нём нельзя ни читать, ни писать.
            log.critical("База дома закрыта", home=home.value, problem=check.describe())
        return check
