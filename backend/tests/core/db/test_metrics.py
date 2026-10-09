"""Pool occupancy per home, and transactions refused when no connection can be had."""

from datetime import timedelta

import pytest

from shosai.core.db.engines import DatabaseProfile
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.metrics import register_pool_occupancy
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.db.tcp_proxy import CountingProxy, Upstream, through
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

TIGHT_POOL = DatabaseProfile(
    pool_size=1, statement_timeout=timedelta(seconds=10), pool_timeout=timedelta(seconds=0.2)
)
UNAVAILABLE = "shosai_db_unavailable_total"


def occupancy(
    access: DatabaseAccess, home: Home
) -> tuple[float | None, float | None, float | None]:
    """In-use and idle connections and the pool size of a home, as Prometheus reads them."""
    labels = {"home": home.value}
    registry = access.registry
    return (
        registry.get_sample_value("shosai_db_pool_connections", {**labels, "state": "in_use"}),
        registry.get_sample_value("shosai_db_pool_connections", {**labels, "state": "idle"}),
        registry.get_sample_value("shosai_db_pool_capacity", labels),
    )


async def test_occupancy_is_read_from_the_pools_at_scrape(run_slot: RunSlot) -> None:
    async with open_database_access(slot_urls(run_slot)) as access:
        register_pool_occupancy(access.registry, access.databases)
        await access.gate.verify_at_start()

        async with access.transactions.begin(TenancyScope(Home.RU), read_only=True):
            during = occupancy(access, Home.RU)
        after = occupancy(access, Home.RU)

    assert during == (1.0, 0.0, 10.0)
    assert after == (0.0, 1.0, 10.0)


async def test_an_exhausted_pool_refuses_fast_and_is_counted(run_slot: RunSlot) -> None:
    shape = ProcessShape(profile=TIGHT_POOL)
    async with open_database_access(slot_urls(run_slot), shape) as access:
        await access.gate.verify_at_start()

        async with access.transactions.begin(TenancyScope(Home.EU), read_only=True):
            with pytest.raises(HomeUnavailableError):
                async with access.transactions.begin(TenancyScope(Home.EU), read_only=True):
                    pytest.fail("второе соединение из пула в один слот не выдаётся")

        refused = access.registry.get_sample_value(
            UNAVAILABLE, {"home": "eu", "reason": "pool_timeout"}
        )

    assert refused == 1.0


async def test_a_home_that_stops_answering_after_the_check_is_refused_and_counted(
    run_slot: RunSlot,
) -> None:
    target = run_slot.claimed.targets(Home.RU).application
    proxy = CountingProxy(Upstream(target.host, target.port))
    port = await proxy.start()
    urls = slot_urls(run_slot)
    urls[Home.RU] = through(urls[Home.RU], port)
    try:
        async with open_database_access(urls) as access:
            await access.gate.verify_at_start()
            await access.databases.engine(Home.RU).dispose()
            proxy.upstream = None

            with pytest.raises(HomeUnavailableError):
                async with access.transactions.begin(TenancyScope(Home.RU)):
                    pytest.fail("транзакция без соединения не открывается")
            refused = access.registry.get_sample_value(
                UNAVAILABLE, {"home": "ru", "reason": "connect_failed"}
            )
    finally:
        await proxy.stop()

    assert refused == 1.0
