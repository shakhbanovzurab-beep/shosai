"""Test database slots: parallel runs never share one, a crashed run does not keep one.

Tests of the locking use their own key (`private_key`), so they neither take nor release
slots that parallel runs need at the same time.
"""

import asyncio
import secrets

import pytest

from shosai.core.kernel.homes import Home
from tests.harness.connections import (
    Connection,
    connect,
    drop_without_goodbye,
    fetch_rows,
    fetch_value,
)
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessConfigurationError, HarnessSettings
from tests.harness.slots import NoFreeSlotError, claim_slot, release_all

HOME_LABELS = {Home.RU: "of the Russian home", Home.EU: "of the EU home"}
HELD_SLOT_LOCKS_SQL = (
    "SELECT count(*) FROM pg_locks "
    "WHERE locktype = 'advisory' AND pid = pg_backend_pid() AND granted"
)
DATABASE_COMMENT_SQL = (
    "SELECT shobj_description(oid, 'pg_database') FROM pg_database "
    "WHERE datname = current_database()"
)
BACKEND_ALIVE_SQL = "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE pid = %s)"
BACKEND_EXIT_POLL_SECONDS = 0.05
BACKEND_EXIT_POLLS = 100


@pytest.fixture
def private_key() -> int:
    """A lock key no other run uses."""
    return secrets.randbelow(2**62)


def all_slots(settings: HarnessSettings) -> range:
    return range(1, settings.database_slots + 1)


async def test_a_run_holds_one_slot_on_each_home_server(run_slot: RunSlot) -> None:
    for home, connection in run_slot.claimed.connections.items():
        database = await fetch_value(connection, "SELECT current_database()")
        comment = await fetch_value(connection, DATABASE_COMMENT_SQL)

        assert database == f"shosai_test_{run_slot.claimed.number}"
        assert isinstance(comment, str)
        assert HOME_LABELS[home] in comment
        assert await fetch_value(connection, HELD_SLOT_LOCKS_SQL) == 1


async def test_a_slot_held_by_a_run_is_not_claimed_by_another(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    held = run_slot.claimed.number

    with pytest.raises(NoFreeSlotError, match=rf"\[{held}\] заняты"):
        await claim_slot(harness_settings, [held])


async def test_concurrent_claims_get_different_slots(
    harness_settings: HarnessSettings, private_key: int
) -> None:
    numbers = all_slots(harness_settings)
    first, second = await asyncio.gather(
        claim_slot(harness_settings, numbers, private_key),
        claim_slot(harness_settings, numbers, private_key),
    )
    try:
        assert first.number != second.number
    finally:
        await asyncio.gather(first.release(), second.release())


async def test_a_released_slot_can_be_claimed_again(
    harness_settings: HarnessSettings, private_key: int
) -> None:
    claimed = await claim_slot(harness_settings, all_slots(harness_settings), private_key)
    await claimed.release()

    reclaimed = await claim_slot(harness_settings, [claimed.number], private_key)
    await reclaimed.release()

    assert reclaimed.number == claimed.number


async def test_a_crashed_run_does_not_keep_its_slot(
    run_slot: RunSlot, harness_settings: HarnessSettings, private_key: int
) -> None:
    crashed = await claim_slot(harness_settings, all_slots(harness_settings), private_key)
    backends = {
        home: connection.info.backend_pid for home, connection in crashed.connections.items()
    }
    for connection in crashed.connections.values():
        drop_without_goodbye(connection)
    for home, pid in backends.items():
        await wait_for_backend_exit(run_slot.claimed.connections[home], pid)

    reclaimed = await claim_slot(harness_settings, [crashed.number], private_key)
    await reclaimed.release()
    for connection in crashed.connections.values():
        await connection.close()

    assert reclaimed.number == crashed.number


async def test_application_role_reaches_the_slot_through_pgbouncer(run_slot: RunSlot) -> None:
    for home in Home:
        target = run_slot.claimed.targets(home).application
        connection = await connect(target)
        try:
            [row] = await fetch_rows(
                connection,
                "SELECT current_database() AS database, current_user AS role, "
                "rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user",
            )
        finally:
            await release_all([connection])

        assert (row["database"], row["role"]) == (target.database, "shosai_app")
        assert not row["rolsuper"]
        assert not row["rolbypassrls"]


async def wait_for_backend_exit(observer: Connection, pid: int) -> None:
    """Wait until the server ends the process of a dropped connection and releases its locks."""
    for _ in range(BACKEND_EXIT_POLLS):
        if not await fetch_value(observer, BACKEND_ALIVE_SQL, (pid,)):
            return
        await asyncio.sleep(BACKEND_EXIT_POLL_SECONDS)
    pytest.fail(f"процесс сервера {pid} жив через 5 с после обрыва соединения")


async def test_a_slot_beyond_the_prepared_databases_is_named(
    harness_settings: HarnessSettings,
) -> None:
    target = harness_settings.homes[Home.RU].migration.for_slot(99)

    with pytest.raises(HarnessConfigurationError, match="нет базы shosai_test_99") as raised:
        await connect(target)

    assert "LOCAL_TEST_DATABASE_COUNT" in str(raised.value)
    assert target.password not in str(raised.value)
