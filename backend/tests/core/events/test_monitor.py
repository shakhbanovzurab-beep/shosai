"""The outbox gauges report each home's backlog and its oldest event (§16.4)."""

from datetime import timedelta

import pytest
from prometheus_client import CollectorRegistry

from tests.core.db.tcp_proxy import CountingProxy, Upstream, through
from tests.core.events.bench import insert_raw_event
from tests.core.kv.outages import closed_port
from tests.core.observability.capture import captured_logs
from tests.harness.database_access import DatabaseAccess, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot
from whisperer.core.events.metrics import EventMetrics
from whisperer.core.events.monitor import OutboxMonitor
from whisperer.core.kernel.homes import Home


def gauges(registry: CollectorRegistry, home: Home) -> tuple[float | None, float | None]:
    """Pending events and the oldest one's age of a home."""
    labels = {"home": home.value}
    return (
        registry.get_sample_value("whisperer_outbox_pending", labels),
        registry.get_sample_value("whisperer_outbox_oldest_age_seconds", labels),
    )


async def test_each_home_reports_its_unpublished_events_and_the_oldest_ones_age(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    ru = run_slot.claimed.connections[Home.RU]
    await insert_raw_event(ru, "probe.note.written", age=timedelta(minutes=10))
    await insert_raw_event(ru, "probe.note.written")
    published = await insert_raw_event(ru, "probe.note.written", age=timedelta(hours=1))
    await ru.execute("UPDATE outbox_messages SET published_at = now() WHERE id = %s", (published,))
    registry = CollectorRegistry()

    answered = await OutboxMonitor(homes.transactions, EventMetrics(registry)).refresh()

    assert answered
    pending, age = gauges(registry, Home.RU)
    assert pending == 2
    assert age is not None
    assert 600 <= age < 660
    assert gauges(registry, Home.EU) == (0, 0)


@pytest.mark.usefixtures("homes")
async def test_a_home_out_of_reach_keeps_its_gauges_and_the_other_home_is_read(
    run_slot: RunSlot,
) -> None:
    await insert_raw_event(run_slot.claimed.connections[Home.EU], "probe.note.written")
    urls = slot_urls(run_slot)
    urls[Home.RU] = through(urls[Home.RU], closed_port())
    registry = CollectorRegistry()

    async with open_database_access(urls) as access:
        await access.gate.verify_at_start()
        answered = await OutboxMonitor(access.transactions, EventMetrics(registry)).refresh()

    assert not answered
    assert gauges(registry, Home.RU) == (None, None)
    pending, _ = gauges(registry, Home.EU)
    assert pending == 1


@pytest.mark.usefixtures("homes")
async def test_a_connection_lost_during_the_read_is_logged_once_and_reported(
    run_slot: RunSlot,
) -> None:
    target = run_slot.claimed.targets(Home.RU).application
    proxy = CountingProxy(Upstream(target.host, target.port))
    urls = slot_urls(run_slot)
    urls[Home.RU] = through(urls[Home.RU], await proxy.start())
    try:
        async with open_database_access(urls) as access:
            await access.gate.verify_at_start()
            monitor = OutboxMonitor(access.transactions, EventMetrics(CollectorRegistry()))
            first = await monitor.refresh()
            await proxy.stop()
            with captured_logs() as logs:
                second = await monitor.refresh()
    finally:
        await proxy.stop()

    assert (first, second) == (True, False)
    [line] = [line for line in logs.lines() if line["message"].startswith("База дома не ответила")]
    assert (line["home"], line["level"]) == ("ru", "warning")
