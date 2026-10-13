"""Live sessions write one cost row per minute, in batches; a replayed batch writes none (F6-C5)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.costs.writer import RECORD_COST
from shosai.core.ai.recording import MeteredCall
from shosai.core.ai.results import Unit, Usage
from shosai.core.ai.sessions.minutes import SessionMeter
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from tests.core.ai.bench import ORG_ID, USER_ID, AiBench, ai_bench, context, set_prices
from tests.core.db.tcp_proxy import through
from tests.core.kv.outages import closed_port
from tests.harness.connections import fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot

LIVE_MODEL = ModelRef(Provider.OPENROUTER, "probe/live")
MINUTE_OF_AUDIO = Usage(units=Decimal(60), unit=Unit.AUDIO_SECOND)


async def minute_rows(run_slot: RunSlot, home: Home = Home.EU) -> list[dict[str, object]]:
    """Cost rows of a home in the order of their minutes."""
    found = await fetch_rows(
        run_slot.claimed.connections[home],
        "SELECT effect_key, kind, created_at, units, cost_usd FROM provider_costs "
        "ORDER BY created_at",
    )
    return [dict(row) for row in found]


async def live_bench(homes: DatabaseAccess) -> AiBench:
    """A bench whose live model has its price per second."""
    await set_prices(homes.transactions, LIVE_MODEL, audio_second="0.0001")
    return ai_bench(homes.transactions)


def open_meter(bench: AiBench, key: str) -> SessionMeter:
    """A meter of a live transcription priced per second, as the port opens it."""
    prices = {Unit.AUDIO_SECOND: Decimal("0.0001")}
    return bench.minutes.open(MeteredCall(context(key), LIVE_MODEL, "live_transcription", prices))


def entry(home: Home, key: str, org: UUID = ORG_ID) -> CostEntry:
    """A minute row of a session in the home."""
    return CostEntry(
        home=home, user_id=USER_ID, org_id=org, cost_id=new_id(), created_at=datetime.now(UTC),
        effect_key=key, provider="openrouter", model="probe/live", kind="live_transcription",
        feature="meetings.capture", call_class="essential", origin="interactive", outcome="ok",
        units=Decimal(60), unit="audio_second", cost_usd=Decimal("0.006"), cost_source="priced",
    )  # fmt: skip


async def test_a_three_minute_stream_writes_one_row_per_minute(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await live_bench(homes)
    meter = open_meter(bench, "stream:s1")
    for _ in range(3):
        meter.add(MINUTE_OF_AUDIO)
        bench.clock.now += 60

    await bench.minutes.close(meter)

    rows = await minute_rows(run_slot)
    assert [row["effect_key"] for row in rows] == ["stream:s1:0", "stream:s1:1", "stream:s1:2"]
    assert {(row["kind"], row["units"], row["cost_usd"]) for row in rows} == {
        ("live_transcription", Decimal("60.000"), Decimal("0.0060000000")),
    }  # fmt: skip
    starts = [row["created_at"] for row in rows]
    assert isinstance(starts[0], datetime)
    assert starts == [starts[0] + timedelta(minutes=minute) for minute in range(3)]
    assert len(bench.settlement.settled) == 3


async def test_usage_within_a_minute_adds_up_to_one_row(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await live_bench(homes)
    meter = open_meter(bench, "stream:s2")
    meter.add(Usage(input_tokens=100, output_tokens=10))
    bench.clock.now += 30
    meter.add(Usage(input_tokens=50, units=Decimal(30), unit=Unit.AUDIO_SECOND))

    await bench.minutes.close(meter)

    [row] = await minute_rows(run_slot)
    assert (row["effect_key"], row["units"]) == ("stream:s2:0", Decimal("30.000"))


async def test_a_flush_writes_the_ended_minutes_and_keeps_the_running_one(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await live_bench(homes)
    meter = open_meter(bench, "stream:s3")
    meter.add(MINUTE_OF_AUDIO)
    bench.clock.now += 61
    meter.add(MINUTE_OF_AUDIO)

    await bench.minutes.flush()
    after_flush = [row["effect_key"] for row in await minute_rows(run_slot)]
    await bench.minutes.close(meter)

    assert after_flush == ["stream:s3:0"]
    assert [row["effect_key"] for row in await minute_rows(run_slot)] == [
        "stream:s3:0", "stream:s3:1",
    ]  # fmt: skip


async def test_a_replayed_batch_writes_nothing_and_settles_nothing_again(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = ai_bench(homes.transactions)
    batch = [entry(Home.EU, f"stream:s4:{minute}") for minute in range(3)]

    await bench.writer.record_many(batch)
    await bench.writer.record_many([entry(Home.EU, row.effect_key) for row in batch])

    assert len(await minute_rows(run_slot)) == 3
    assert len(bench.settlement.settled) == 3
    assert bench.sample("shosai_ai_cost_rows_recorded_total", source="priced") == 3


# Фикстура homes очищает базы слота после теста: строка EU пишется в обход неё.
@pytest.mark.usefixtures("homes")
async def test_a_batch_writes_each_company_apart_and_defers_a_home_that_is_down(
    run_slot: RunSlot,
) -> None:
    urls = slot_urls(run_slot)
    urls[Home.RU] = through(urls[Home.RU], closed_port())
    async with open_database_access(urls) as cut_off:
        await cut_off.gate.verify_at_start()
        bench = ai_bench(cut_off.transactions)
        await bench.writer.record_many(
            [entry(Home.RU, "stream:ru:0"), entry(Home.EU, "stream:eu:0", org=new_id())]
        )

    [(task, deferred)] = bench.sender.sent
    eu_rows = await minute_rows(run_slot)
    assert (task, getattr(deferred, "effect_key", None)) == (RECORD_COST.name, "stream:ru:0")
    assert [row["effect_key"] for row in eu_rows] == ["stream:eu:0"]
    assert (
        await fetch_value(
            run_slot.claimed.connections[Home.RU], "SELECT count(*) FROM provider_costs"
        )
        == 0
    )


async def test_open_sessions_are_written_when_the_process_stops(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await live_bench(homes)

    async with bench.minutes.running():
        meter = open_meter(bench, "stream:s5")
        meter.add(MINUTE_OF_AUDIO)

    assert [row["effect_key"] for row in await minute_rows(run_slot)] == ["stream:s5:0"]


async def test_a_session_key_leaves_room_for_the_minute(homes: DatabaseAccess) -> None:
    bench = await live_bench(homes)

    with pytest.raises(ValueError, match="минуты"):
        open_meter(bench, "s" * 195)
