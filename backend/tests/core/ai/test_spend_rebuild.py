"""The counter rebuild: every counter restored, and each row counted once while rows arrive."""

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.spend.counters import REBUILD_MARK, REBUILD_PENDING
from shosai.core.ai.spend.guard import SpendGuard, SpendMetrics
from shosai.core.ai.spend.kill_switch import KillSwitch
from shosai.core.ai.spend.rebuild import CounterRebuild, RebuildBusyError, rebuild_spend_counters
from shosai.core.kernel.homes import Home
from tests.core.ai.bench import OPEN_CEILINGS, Doubles, ai_bench
from tests.core.ai.test_spend_reports import row
from tests.harness.database_access import DatabaseAccess

NOW = datetime.now(UTC)
GLOBAL_DAY = f"shosai:ai:spend:global:day:{NOW:%Y%m%d}"


def text_keys(found: Sequence[bytes | str]) -> list[str]:
    """Keys of the spend counters as text, reservations left out."""
    keys = [key.decode() if isinstance(key, bytes) else key for key in found]
    return sorted(key for key in keys if not key.endswith(":held"))


async def test_the_rebuild_restores_every_counter_after_valkey_is_emptied(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    writer = ai_bench(homes.transactions, doubles=Doubles(valkey=valkey)).writer
    for entry in (
        row(Home.RU, NOW, "0.30"),
        row(Home.EU, NOW, "0.20", origin="background"),
        row(Home.EU, NOW, "0.05", call_class="essential"),
    ):
        await writer.write(entry)
    keys = text_keys(await valkey.keys("shosai:ai:spend:*"))
    counted = {key: await valkey.get(key) for key in keys}

    await valkey.flushdb()
    written = await rebuild_spend_counters(homes.transactions, valkey, NOW)

    assert written == len(keys)
    assert {key: await valkey.get(key) for key in keys} == counted
    assert counted[GLOBAL_DAY] == b"550000"
    assert await valkey.exists(REBUILD_MARK, REBUILD_PENDING) == 0


def guard(valkey: Redis) -> SpendGuard:
    """The counting side of spend control over the slot's Valkey."""
    return SpendGuard(
        valkey, OPEN_CEILINGS, KillSwitch(valkey, forced=False), SpendMetrics(CollectorRegistry())
    )


async def test_a_row_committed_before_the_snapshot_and_counted_during_it_is_counted_once(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    # Строка закоммичена, но счётчиков ещё не коснулась: писатель медлит после коммита.
    late = row(Home.EU, NOW, "0.40")
    await ai_bench(homes.transactions).writer.write(late)
    rebuild = CounterRebuild(homes.transactions, valkey, NOW)

    await rebuild.start()
    await guard(valkey).count([late])
    await rebuild.finish()

    assert await valkey.get(GLOBAL_DAY) == b"400000"


async def test_a_row_recorded_while_the_rebuild_runs_is_counted_once(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    writer = ai_bench(homes.transactions, doubles=Doubles(valkey=valkey)).writer
    await writer.write(row(Home.RU, NOW, "0.10"))
    rebuild = CounterRebuild(homes.transactions, valkey, NOW)

    await rebuild.start()
    await writer.write(row(Home.EU, NOW, "0.25"))
    await rebuild.finish()
    await writer.write(row(Home.EU, NOW, "0.05"))

    assert await valkey.get(GLOBAL_DAY) == b"400000"


async def test_a_row_counted_but_absent_from_the_snapshot_is_added(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    rebuild = CounterRebuild(homes.transactions, valkey, NOW)
    await rebuild.start()
    # Строка в списке ожидания, но её дом ещё не показывает: она прибавляется по описанию.
    unseen: CostEntry = row(Home.EU, NOW, "0.15")
    await guard(valkey).count([unseen])

    await rebuild.finish()

    assert await valkey.get(GLOBAL_DAY) == b"150000"


async def test_a_second_rebuild_waits_for_the_first(homes: DatabaseAccess, valkey: Redis) -> None:
    first = CounterRebuild(homes.transactions, valkey, NOW)
    await first.start()

    with pytest.raises(RebuildBusyError):
        await rebuild_spend_counters(homes.transactions, valkey, NOW)
    await first.finish()

    assert await valkey.exists(REBUILD_MARK) == 0
