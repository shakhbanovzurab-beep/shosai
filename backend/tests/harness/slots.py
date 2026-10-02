"""Claiming a test database slot with an advisory lock (ADR 0009, item 3).

Slot `N` is the database `whisperer_test_<N>` in every home. A run holds a direct
migration-role connection to each of them with a session lock on it; a crashed run
loses its connections and PostgreSQL releases its locks by itself.
"""

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

from tests.harness.connections import Connection, connect, fetch_value
from tests.harness.guards import ensure_prepared_test_database
from tests.harness.settings import DatabaseTarget, HarnessSettings, HomeTargets
from whisperer.core.kernel.homes import Home

# Один ключ у всех прогонов: блокировку слота видят все, кто его ищет.
SLOT_LOCK_KEY: Final = 0x5768_6973_7065_7254
DATABASE_COMMENT_SQL: Final = (
    "SELECT shobj_description(oid, 'pg_database') FROM pg_database "
    "WHERE datname = current_database()"
)
TRY_LOCK_SQL: Final = "SELECT pg_try_advisory_lock(%s)"
UNLOCK_ALL_SQL: Final = "SELECT pg_advisory_unlock_all()"


class NoFreeSlotError(Exception):
    """Every slot in the list is held by other runs."""


@dataclass(frozen=True, slots=True)
class ClaimedSlot:
    """A slot claimed by a run: its number and the migration-role connection per home."""

    number: int
    settings: HarnessSettings
    connections: Mapping[Home, Connection]

    def targets(self, home: Home) -> HomeTargets:
        """The slot's database addresses in a home for the application and migration roles."""
        home_targets = self.settings.homes[home]
        return HomeTargets(
            application=home_targets.application.for_slot(self.number),
            migration=home_targets.migration.for_slot(self.number),
        )

    async def release(self) -> None:
        """Release the slot's locks and close the connections."""
        await release_all(self.connections.values())


async def claim_slot(
    settings: HarnessSettings, numbers: Iterable[int], lock_key: int = SLOT_LOCK_KEY
) -> ClaimedSlot:
    """Claim the first slot free in both homes; otherwise raise NoFreeSlotError.

    Another `lock_key` gives a separate claim space, so tests of the locking itself do
    not take slots that parallel runs need.
    """
    tried: list[int] = []
    for number in numbers:
        tried.append(number)
        connections = await _lock_in_every_home(settings, number, lock_key)
        if connections is not None:
            return ClaimedSlot(number=number, settings=settings, connections=connections)
    message = (
        f"все слоты тестовых баз {tried} заняты другими прогонами; "
        "дождитесь их или увеличьте TEST_DATABASE_SLOTS и LOCAL_TEST_DATABASE_COUNT"
    )
    raise NoFreeSlotError(message)


async def release_all(connections: Iterable[Connection]) -> None:
    """Release connections in parallel; the first error is raised after all of them."""
    results = await asyncio.gather(
        *(_release(connection) for connection in connections), return_exceptions=True
    )
    for result in results:
        if isinstance(result, BaseException):
            raise result


async def _release(connection: Connection) -> None:
    """Release locks explicitly: after a close the server frees them only once its process exits."""
    try:
        if not connection.closed:
            await connection.execute(UNLOCK_ALL_SQL)
    finally:
        await connection.close()


async def _lock_in_every_home(
    settings: HarnessSettings, number: int, lock_key: int
) -> dict[Home, Connection] | None:
    """Lock the slot in every home in turn; if one refuses, release the others."""
    held: dict[Home, Connection] = {}
    try:
        for home in Home:
            target = settings.homes[home].migration.for_slot(number)
            connection = await _lock_database(target, lock_key)
            if connection is None:
                await release_all(held.values())
                return None
            held[home] = connection
    except BaseException:
        await release_all(held.values())
        raise
    return held


async def _lock_database(target: DatabaseTarget, lock_key: int) -> Connection | None:
    """Check the prepared-database mark and try to take the slot lock without waiting."""
    connection = await connect(target)
    try:
        comment = await fetch_value(connection, DATABASE_COMMENT_SQL)
        ensure_prepared_test_database(target, comment if isinstance(comment, str) else None)
        locked = await fetch_value(connection, TRY_LOCK_SQL, (lock_key,))
    except BaseException:
        await connection.close()
        raise
    if locked is True:
        return connection
    await connection.close()
    return None
