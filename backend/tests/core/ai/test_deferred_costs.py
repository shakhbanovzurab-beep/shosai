"""A row its home refuses goes to a task; with Valkey out too, it is counted lost (F6-C6)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.costs.writer import RECORD_COST, record_cost_handler
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from tests.core.ai.bench import ORG_ID, USER_ID, ai_bench
from tests.core.db.tcp_proxy import through
from tests.core.kv.outages import closed_port
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot


def entry(home: Home) -> CostEntry:
    """A paid call's row in the home."""
    return CostEntry(
        home=home, user_id=USER_ID, org_id=ORG_ID, cost_id=new_id(),
        created_at=datetime.now(UTC), effect_key="stage:run-7:notes:1", provider="openrouter",
        model="probe/chat", kind="chat", feature="notes.findings", call_class="essential",
        origin="background", outcome="ok", input_tokens=900, output_tokens=300,
        cost_usd=Decimal("0.0042"), cost_source="reported",
    )  # fmt: skip


async def test_a_row_its_home_refuses_is_deferred_and_written_once_later(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    urls = slot_urls(run_slot)
    urls[Home.RU] = through(urls[Home.RU], closed_port())
    row = entry(Home.RU)
    async with open_database_access(urls) as cut_off:
        await cut_off.gate.verify_at_start()
        down = ai_bench(cut_off.transactions)
        await down.writer.record(row)
        with pytest.raises(HomeUnavailableError):
            await down.writer.write(row)

    [(task, deferred)] = down.sender.sent
    assert isinstance(deferred, CostEntry)
    deliver = record_cost_handler(ai_bench(homes.transactions).writer)
    # Повторная доставка задачи — тот же ключ эффекта: строка одна.
    for _ in range(2):
        await deliver.handle(deferred)

    count = await fetch_value(
        run_slot.claimed.connections[Home.RU], "SELECT count(*) FROM provider_costs"
    )
    assert (task, deferred) == (RECORD_COST.name, row)
    assert count == 1
    assert down.sample("shosai_ai_cost_rows_deferred_total") == 1


async def test_with_its_home_and_valkey_out_the_cost_is_counted_lost(run_slot: RunSlot) -> None:
    urls = slot_urls(run_slot)
    urls[Home.EU] = through(urls[Home.EU], closed_port())
    async with open_database_access(urls) as cut_off:
        await cut_off.gate.verify_at_start()
        down = ai_bench(cut_off.transactions)
        down.sender.failing = True
        await down.writer.record(entry(Home.EU))

    assert down.sender.sent == []
    assert down.sample("shosai_ai_calls_without_cost_row_total") == 1
