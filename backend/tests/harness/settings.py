"""Settings of a test run: only variables prefixed with `TEST_` (ADR 0009, item 1).

Runtime variables (`HOME_RU_DATABASE_URL`, `DATABASE_URL` and the rest) are never read
here: without `TEST_*` the run fails instead of reaching a working database.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Self
from urllib.parse import quote, unquote, urlsplit

from pydantic import SecretStr

from whisperer.core.kernel.homes import Home

DATABASE_URL_SCHEME = "postgresql"
TEST_DATABASE_NAME = "whisperer_test"
DATABASE_SLOTS_VARIABLE = "TEST_DATABASE_SLOTS"
# Valkey держит 16 логических баз, база 0 — у разработки: слотов не больше 15.
MAX_DATABASE_SLOTS = 15
DEFAULT_POSTGRES_PORT = 5432
SETUP_HINT = (
    "задайте переменные TEST_* (.env.example, раздел 3) и запускайте "
    "`uv run --env-file ../.env pytest`"
)


class HarnessConfigurationError(Exception):
    """TEST_* variables are missing or malformed; the message never reveals their values."""


def application_variable(home: Home) -> str:
    """Name of the variable with the home's application-role URL (through PgBouncer)."""
    return f"TEST_HOME_{home.name}_DATABASE_URL"


def migration_variable(home: Home) -> str:
    """Name of the variable with the home's migration-role URL (directly to PostgreSQL)."""
    return f"TEST_HOME_{home.name}_MIGRATION_DATABASE_URL"


@dataclass(frozen=True, slots=True)
class DatabaseTarget:
    """Address of one database; `variable` is where it was read from, for messages."""

    variable: str
    host: str
    port: int
    user: str
    password: str = field(repr=False)
    database: str

    def for_slot(self, slot: int) -> Self:
        """The same database with the slot number: `whisperer_test` → `whisperer_test_<slot>`."""
        return type(self)(
            variable=self.variable,
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=f"{self.database}_{slot}",
        )

    def url(self) -> SecretStr:
        """The address in the application's format, for the settings of the code under test."""
        credentials = f"{quote(self.user, safe='')}:{quote(self.password, safe='')}"
        host = f"[{self.host}]" if ":" in self.host else self.host
        return SecretStr(
            f"{DATABASE_URL_SCHEME}://{credentials}@{host}:{self.port}/{quote(self.database)}"
        )


@dataclass(frozen=True, slots=True)
class HomeTargets:
    """The two roles of one home: the application through PgBouncer, migrations directly."""

    application: DatabaseTarget
    migration: DatabaseTarget


@dataclass(frozen=True, slots=True)
class HarnessSettings:
    """Everything the harness knows about test databases: both homes' URLs and the slot count."""

    homes: Mapping[Home, HomeTargets]
    database_slots: int

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> Self:
        """Read the settings from the environment; on any error list every problem at once."""
        problems: list[str] = []
        homes: dict[Home, HomeTargets] = {}
        for home in Home:
            application = _read_target(environ, application_variable(home), problems)
            migration = _read_target(environ, migration_variable(home), problems)
            if application is not None and migration is not None:
                homes[home] = HomeTargets(application=application, migration=migration)
        database_slots = _read_slots(environ, problems)
        if problems:
            raise HarnessConfigurationError("\n".join([*problems, SETUP_HINT]))
        return cls(homes=homes, database_slots=database_slots)

    def database_variables(self) -> tuple[str, ...]:
        """Names of every database URL variable the harness read."""
        return tuple(
            target.variable
            for targets in self.homes.values()
            for target in (targets.application, targets.migration)
        )


def parse_database_url(variable: str, url: str) -> DatabaseTarget:
    """Parse a URL of the form `postgresql://user:password@host:port/database`."""
    parts = urlsplit(url)
    if parts.scheme != DATABASE_URL_SCHEME:
        message = f"{variable}: схема адреса должна быть {DATABASE_URL_SCHEME}"
        raise HarnessConfigurationError(message)
    if parts.query or parts.fragment:
        message = f"{variable}: параметры после ? и # харнесс не поддерживает"
        raise HarnessConfigurationError(message)
    try:
        port = parts.port or DEFAULT_POSTGRES_PORT
    except ValueError as error:
        message = f"{variable}: неверный порт"
        raise HarnessConfigurationError(message) from error
    if not parts.hostname or not parts.username or parts.password is None:
        message = f"{variable}: в адресе нужны хост, пользователь и пароль"
        raise HarnessConfigurationError(message)
    return DatabaseTarget(
        variable=variable,
        host=parts.hostname,
        port=port,
        user=unquote(parts.username),
        password=unquote(parts.password),
        database=unquote(parts.path.removeprefix("/")),
    )


def _read_target(
    environ: Mapping[str, str], variable: str, problems: list[str]
) -> DatabaseTarget | None:
    url = environ.get(variable)
    if not url:
        problems.append(f"{variable}: не задана")
        return None
    try:
        return parse_database_url(variable, url)
    except HarnessConfigurationError as error:
        problems.append(str(error))
        return None


def _read_slots(environ: Mapping[str, str], problems: list[str]) -> int:
    raw = environ.get(DATABASE_SLOTS_VARIABLE)
    if not raw:
        problems.append(f"{DATABASE_SLOTS_VARIABLE}: не задана")
        return 0
    if not raw.isdecimal() or not 1 <= int(raw) <= MAX_DATABASE_SLOTS:
        problems.append(f"{DATABASE_SLOTS_VARIABLE}: ожидается целое от 1 до {MAX_DATABASE_SLOTS}")
        return 0
    return int(raw)
