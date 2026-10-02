"""The harness's direct connections to the test databases and its SQL files."""

from functools import cache
from pathlib import Path
from typing import Final

import asyncpg

from tests.harness.settings import DatabaseTarget, HarnessConfigurationError

type Connection = asyncpg.Connection[asyncpg.Record]

CONNECT_TIMEOUT_SECONDS: Final = 5.0
APPLICATION_NAME: Final = "whisperer-tests"
SQL_DIRECTORY: Final = Path(__file__).parent


async def connect(target: DatabaseTarget) -> Connection:
    """Open a connection without a statement cache, the only kind PgBouncer allows (ADR 0001)."""
    try:
        return await asyncpg.connect(
            host=target.host,
            port=target.port,
            user=target.user,
            password=target.password,
            database=target.database,
            timeout=CONNECT_TIMEOUT_SECONDS,
            statement_cache_size=0,
            server_settings={"application_name": APPLICATION_NAME},
        )
    except asyncpg.InvalidCatalogNameError as error:
        message = (
            f"{target.variable}: на {target.host}:{target.port} нет базы {target.database}; "
            "TEST_DATABASE_SLOTS больше числа подготовленных баз (LOCAL_TEST_DATABASE_COUNT)"
        )
        raise HarnessConfigurationError(message) from error


@cache
def load_sql(name: str) -> str:
    """Text of a harness SQL file, read once per run."""
    return (SQL_DIRECTORY / name).read_text(encoding="utf-8")
