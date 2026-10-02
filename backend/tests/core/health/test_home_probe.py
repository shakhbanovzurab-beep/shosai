"""The readiness probe of a home's database: its own pool, and `down` for a closed home."""

import pytest

from tests.core.db.tcp_proxy import CountingProxy, through
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot
from whisperer.core.db.home_checks import HomeMisconfiguredError
from whisperer.core.db.migrations import MigrationHistory
from whisperer.core.health.dependencies import home_probe
from whisperer.core.health.probes import probe_dependencies
from whisperer.core.kernel.homes import Home

FUTURE_REVISION = "f1f1f1f1f1f1"


async def test_both_homes_answer(database_access: DatabaseAccess) -> None:
    probes = [home_probe(home, database_access.databases, database_access.gate) for home in Home]

    assert await probe_dependencies(probes) == {"homes.ru": "ok", "homes.eu": "ok"}


async def test_a_home_out_of_reach_is_down_and_the_other_is_not(run_slot: RunSlot) -> None:
    proxy = CountingProxy(None)
    urls = slot_urls(run_slot)
    urls[Home.RU] = through(urls[Home.RU], await proxy.start())
    try:
        async with open_database_access(urls) as access:
            probes = [home_probe(home, access.databases, access.gate) for home in Home]
            statuses = await probe_dependencies(probes)
    finally:
        await proxy.stop()

    assert statuses == {"homes.ru": "down", "homes.eu": "ok"}


async def test_a_home_the_check_closed_is_down_although_it_answers(run_slot: RunSlot) -> None:
    applied = MigrationHistory.load()
    ahead = MigrationHistory(head=FUTURE_REVISION, revisions=applied.revisions | {FUTURE_REVISION})

    async with open_database_access(slot_urls(run_slot), ProcessShape(history=ahead)) as access:
        with pytest.raises(HomeMisconfiguredError):
            await access.gate.verify_at_start()
        statuses = await probe_dependencies(
            [home_probe(home, access.databases, access.gate) for home in Home]
        )

    assert statuses == {"homes.ru": "down", "homes.eu": "down"}
