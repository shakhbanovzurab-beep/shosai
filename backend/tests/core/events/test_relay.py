"""The relay passes each event to every subscriber once, home by home (§12, §14 rule 1)."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from tests.core.db.tcp_proxy import through
from tests.core.events.bench import (
    Applied,
    NoteArchived,
    event_bench,
    outbox_rows,
    recording,
)
from tests.core.events.relay_bench import RecordingSender, write_notes
from tests.core.kv.outages import closed_port
from tests.harness.database_access import DatabaseAccess, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot
from whisperer.core.db.errors import HomeUnavailableError
from whisperer.core.events.metrics import EventMetrics
from whisperer.core.events.relay import OutboxRelay, RelayPass
from whisperer.core.events.relay_limits import RelayLimits
from whisperer.core.events.resources import EventResources
from whisperer.core.kernel.homes import Home
from whisperer.core.kernel.tenancy import TenancyScope


class RelayStoppedError(Exception):
    """The process running a relay pass died in the middle of it."""


async def test_a_pass_queues_one_delivery_per_subscriber_outside_any_transaction(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    applied = Applied()
    subscribers = [recording("mail.welcome", applied), recording("search.index_note", applied)]
    bench = event_bench(valkey, homes, subscribers)
    ids = await write_notes(homes.transactions, bench.outbox, Home.RU, 3)
    sender = RecordingSender(homes.databases)
    relay = OutboxRelay(bench.resources, sender)

    first = await relay.relay(Home.RU)
    second = await relay.relay(Home.RU)

    assert first == RelayPass(published=ids)
    assert second == RelayPass()
    assert [(task, payload.event_id) for task, payload in sender.sent] == [
        (task, event_id)
        for event_id in ids
        for task in ("events.mail.welcome", "events.search.index_note")
    ]
    assert sender.held_connections == [0] * 6
    rows = await outbox_rows(run_slot.claimed.connections[Home.RU])
    assert [(row["published"], row["attempts"]) for row in rows] == [(True, 0)] * 3
    assert bench.sample("whisperer_outbox_published_total", home="ru") == 3


async def test_an_event_nobody_subscribes_to_is_published_without_deliveries(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = event_bench(valkey, homes, [recording("mail.welcome", Applied())])
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        archived = await bench.outbox.add(session, NoteArchived(record_id=uuid.uuid4()))
    sender = RecordingSender(homes.databases)

    result = await OutboxRelay(bench.resources, sender).relay(Home.EU)

    assert result == RelayPass(published=[archived])
    assert sender.sent == []


async def test_rows_a_pass_holds_are_skipped_by_a_concurrent_pass(
    valkey: Redis, homes: DatabaseAccess
) -> None:
    bench = event_bench(valkey, homes, [recording("mail.welcome", Applied())])
    ids = await write_notes(homes.transactions, bench.outbox, Home.EU, 2)
    concurrent: list[RelayPass] = []

    async def run_concurrent_pass() -> None:
        other = OutboxRelay(bench.resources, RecordingSender(homes.databases))
        concurrent.append(await other.relay(Home.EU))

    sender = RecordingSender(homes.databases, before_first_send=run_concurrent_pass)
    first = await OutboxRelay(bench.resources, sender).relay(Home.EU)

    assert concurrent == [RelayPass()]
    assert first == RelayPass(published=ids)


async def test_rows_of_a_pass_that_died_return_when_the_lease_ends(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    lease = timedelta(milliseconds=300)
    bench = event_bench(
        valkey, homes, [recording("mail.welcome", Applied())], relay_limits=RelayLimits(lease=lease)
    )
    [event_id] = await write_notes(homes.transactions, bench.outbox, Home.RU, 1)
    dying = RecordingSender(homes.databases, failures={1: RelayStoppedError()})

    with pytest.raises(RelayStoppedError):
        await OutboxRelay(bench.resources, dying).relay(Home.RU)
    [claimed] = await outbox_rows(run_slot.claimed.connections[Home.RU])
    early = await OutboxRelay(bench.resources, RecordingSender(homes.databases)).relay(Home.RU)
    await run_slot.claimed.connections[Home.RU].execute("SELECT pg_sleep(%s)", (0.35,))
    late = await OutboxRelay(bench.resources, RecordingSender(homes.databases)).relay(Home.RU)

    assert (claimed["published"], claimed["attempts"]) == (False, 0)
    assert 0 < claimed["due_in"] <= lease.total_seconds()
    assert early == RelayPass()
    assert late == RelayPass(published=[event_id])


async def test_each_home_relays_only_its_own_events(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = event_bench(valkey, homes, [recording("mail.welcome", Applied())])
    ru_ids = await write_notes(homes.transactions, bench.outbox, Home.RU, 2)
    eu_ids = await write_notes(homes.transactions, bench.outbox, Home.EU, 1)
    sender = RecordingSender(homes.databases)
    relay = OutboxRelay(bench.resources, sender)

    ru_pass = await relay.relay(Home.RU)
    eu_rows = await outbox_rows(run_slot.claimed.connections[Home.EU])
    eu_pass = await relay.relay(Home.EU)

    assert ru_pass == RelayPass(published=ru_ids)
    assert [row["published"] for row in eu_rows] == [False]
    assert eu_pass == RelayPass(published=eu_ids)
    assert [payload.home for _, payload in sender.sent] == [Home.RU, Home.RU, Home.EU]


async def test_a_home_out_of_reach_stops_only_its_own_relay(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = event_bench(valkey, homes, [recording("mail.welcome", Applied())])
    eu_ids = await write_notes(homes.transactions, bench.outbox, Home.EU, 1)
    urls = slot_urls(run_slot)
    urls[Home.RU] = through(urls[Home.RU], closed_port())

    async with open_database_access(urls) as access:
        await access.gate.verify_at_start()
        resources = EventResources(
            catalog=bench.resources.catalog,
            transactions=access.transactions,
            metrics=EventMetrics(CollectorRegistry()),
            tracer_provider=TracerProvider(),
        )
        relay = OutboxRelay(resources, RecordingSender(access.databases))
        with pytest.raises(HomeUnavailableError):
            await relay.relay(Home.RU)
        eu_pass = await relay.relay(Home.EU)

    assert eu_pass == RelayPass(published=eu_ids)


@pytest.mark.parametrize(
    "limits",
    [{"batch": 0}, {"lease": timedelta(0)}, {"longest_pause": timedelta(seconds=-1)}],
)
def test_relay_limits_are_positive(limits: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="relay"):
        RelayLimits(**limits)
