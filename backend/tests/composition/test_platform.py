"""The platform builds every listed slice in order, wires each part and closes in reverse."""

import uuid

import pytest
from sqlalchemy import func, select

from shosai.composition.startup import StartFailedError
from shosai.core.events.records import OutboxMessage
from shosai.core.health.probes import probe_dependencies
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.queues import TaskQueue
from tests.composition.fixture_features import (
    TIDY_NOTES,
    Lifecycle,
    NoteWritten,
    broken_feature,
    digest_feature,
    notes_feature,
)
from tests.composition.platform_bench import platform_over_slot
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

CORE_PROBES = ["homes.ru", "homes.eu", "valkey", "cache", "storage.ru", "storage.eu"]


async def test_every_part_of_every_slice_is_wired_and_closed_in_reverse(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    lifecycle = Lifecycle()
    features = (notes_feature(lifecycle), digest_feature(lifecycle))

    async with platform_over_slot(run_slot, harness_settings, features) as bench:
        built = list(lifecycle.events)
        platform = bench.platform
        default = platform.tasks.brokers[TaskQueue.DEFAULT]
        statuses = await probe_dependencies(platform.probes)
        [route] = platform.events.catalog.routes_of(NoteWritten.event_type) or ()

    assert built == ["notes:open:api", "digest:open"]
    assert lifecycle.events[-2:] == ["digest:close", "notes:close"]
    assert default.declaration(TIDY_NOTES.name) is TIDY_NOTES
    assert default.declaration("events.digest.collect") is route.task
    assert platform.tasks.brokers[TaskQueue.CRITICAL].declaration("events.relay_outbox")
    assert [probe.name for probe in platform.probes] == [*CORE_PROBES, "notes.index"]
    assert set(statuses.values()) == {"ok"}
    assert [loop.name for loop in platform.parts.loops] == ["notes.sweep"]
    # HTTP: маршруты ссылок из писем (ядро) и маршрутизатор среза.
    assert (len(platform.parts.http_routers), len(platform.parts.ws_routers)) == (2, 1)


async def test_a_slice_writes_its_listed_events_through_the_outbox(
    run_slot: RunSlot, harness_settings: HarnessSettings, homes: DatabaseAccess
) -> None:
    lifecycle = Lifecycle()
    features = (notes_feature(lifecycle), digest_feature(lifecycle))

    async with platform_over_slot(run_slot, harness_settings, features) as bench:
        services = bench.platform.services
        async with services.transactions.begin(TenancyScope(Home.EU)) as session:
            await services.outbox.add(session, NoteWritten(note_id=uuid.uuid7()))
        async with homes.transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
            written = await session.scalar(select(func.count()).select_from(OutboxMessage))

    assert written == 1


async def test_a_slice_that_fails_to_build_stops_the_start_and_the_others_close(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    lifecycle = Lifecycle()
    features = (notes_feature(lifecycle), broken_feature(lifecycle), digest_feature(lifecycle))

    with pytest.raises(StartFailedError) as raised:
        async with platform_over_slot(run_slot, harness_settings, features):
            pytest.fail("платформа со сломанным срезом не должна открыться")

    assert raised.value.step == "feature:broken"
    assert lifecycle.events == ["notes:open:api", "broken:open", "notes:close"]


async def test_a_slice_listed_twice_stops_the_start(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    lifecycle = Lifecycle()
    features = (notes_feature(lifecycle), notes_feature(lifecycle))

    with pytest.raises(StartFailedError) as raised:
        async with platform_over_slot(run_slot, harness_settings, features):
            pytest.fail("срез, перечисленный дважды, не должен собраться")

    assert raised.value.step == "features"
    assert "notes" in str(raised.value.__cause__)


async def test_two_probes_with_one_name_stop_the_start(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    lifecycle = Lifecycle()
    features = (notes_feature(lifecycle, probe_name="valkey"),)

    with pytest.raises(StartFailedError) as raised:
        async with platform_over_slot(run_slot, harness_settings, features):
            pytest.fail("две пробы с одним именем не должны собраться")

    assert raised.value.step == "probes"
    assert lifecycle.events[-1] == "notes:close"
