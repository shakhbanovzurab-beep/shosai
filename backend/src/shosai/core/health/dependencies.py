"""Probes of the dependencies of a process: each home's database and bucket, Valkey, the cache."""

from typing import Final

from redis.asyncio import Redis
from sqlalchemy import exc, text

from shosai.core.db.engines import HomeDatabases
from shosai.core.db.home_checks import HomeGate
from shosai.core.health.probes import DependencyProbe
from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.storage.errors import StorageRejectedError, StorageUnavailableError
from shosai.core.storage.port import ObjectStorage

PING_STATEMENT: Final = text("SELECT 1")
# Отказ соединения, исчерпанный пул и оборванное соединение — база дома недоступна.
DATABASE_FAILURES: Final = (exc.OperationalError, exc.InterfaceError, exc.TimeoutError)


class HomeClosedError(Exception):
    """The start check closed the home: its database is another home's or behind the code."""


def home_probe_name(home: Home) -> str:
    """`homes.ru`, `homes.eu`: the name of a home's database in the readiness report."""
    return f"homes.{home.value}"


def home_probe(home: Home, databases: HomeDatabases, gate: HomeGate) -> DependencyProbe:
    """One statement through the home's own pool; a home the check closed is down too."""

    async def check() -> None:
        if gate.is_closed(home):
            message = f"дом {home.value} закрыт проверкой базы"
            raise HomeClosedError(message)
        async with databases.engine(home).connect() as connection:
            await connection.execute(PING_STATEMENT)

    return DependencyProbe(
        name=home_probe_name(home), check=check, failures=(*DATABASE_FAILURES, HomeClosedError)
    )


def redis_probe(name: str, client: Redis) -> DependencyProbe:
    """`PING` to a Redis-protocol server: Valkey or the cache."""
    return DependencyProbe(name=name, check=client.ping, failures=REDIS_FAILURES)


def storage_probe(home: Home, storage: ObjectStorage) -> DependencyProbe:
    """`HeadBucket` on a home's bucket: reachable, and the credentials still open it."""
    return DependencyProbe(
        name=f"storage.{home.value}",
        check=storage.ping,
        failures=(StorageUnavailableError, StorageRejectedError),
    )
