"""The invariant monitor: every billed call has its cost row, hour by hour, home by home."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.ai.costs.billing import BillingMarks, hour_of
from shosai.core.ai.costs.reconciliation import RECONCILE_LAG, CostReconciliation
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from shosai.core.kernel.homes import Home
from tests.core.ai.bench import (
    CHAT_MODEL,
    ROUTE,
    AiBench,
    Doubles,
    ai_bench,
    context,
    set_prices,
    unreachable_valkey,
)
from tests.core.ai.test_minutes import entry
from tests.doubles.openrouter import chat_answer, usage
from tests.harness.database_access import DatabaseAccess

QUESTION = ChatRequest(messages=(ChatMessage(Role.USER, (TextPart("Hi?"),)),), max_output_tokens=20)


class Monitor:
    """The reconciliation of the slot's homes over the run's Valkey."""

    def __init__(self, homes: DatabaseAccess, valkey: Redis) -> None:
        self.registry = CollectorRegistry()
        self.marks = BillingMarks(valkey, self.registry)
        self.reconciliation = CostReconciliation(homes.transactions, self.marks, self.registry)

    async def missing_now(self, home: Home = Home.EU) -> int | None:
        """Reconcile the current hour, as the job will two hours from now."""
        return await self.reconciliation.reconcile(home, datetime.now(UTC) + RECONCILE_LAG)

    def gauge(self, home: Home = Home.EU) -> float | None:
        """The monitor's gauge of the home."""
        return self.registry.get_sample_value("shosai_ai_cost_rows_missing", {"home": home.value})


async def chat_bench(homes: DatabaseAccess, valkey: Redis) -> AiBench:
    """A priced chat model over the run's Valkey."""
    await set_prices(
        homes.transactions, CHAT_MODEL, input_token="0.000001", output_token="0.000004"
    )
    return ai_bench(homes.transactions, doubles=Doubles(valkey=valkey))


async def test_billed_calls_and_their_repeats_reconcile_to_zero(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await chat_bench(homes, valkey)
    monitor = Monitor(homes, valkey)
    for _ in range(3):
        bench.openrouter.answer("chat/completions", chat_answer("Hi.", usage(10, 2, cost=0.001)))

    for key in ("turn:1", "turn:2", "turn:1"):
        await bench.providers.chat(context(key), ROUTE, QUESTION)
    marks = await monitor.marks.of_hour(Home.EU, datetime.now(UTC))

    assert (marks.billed, marks.repeated) == (3, 1)
    assert await monitor.missing_now() == 0
    assert monitor.gauge() == 0
    assert bench.sample("shosai_ai_calls_billed_total", provider="openrouter", kind="chat",
                        call_class="standard") == 3  # fmt: skip
    assert bench.sample("shosai_ai_cost_microusd_total", provider="openrouter",
                        call_class="standard") == 2000  # fmt: skip


async def test_a_planted_missing_row_is_reported(homes: DatabaseAccess, valkey: Redis) -> None:
    bench = await chat_bench(homes, valkey)
    monitor = Monitor(homes, valkey)
    bench.openrouter.answer("chat/completions", chat_answer("Hi.", usage(10, 2, cost=0.001)))
    await bench.providers.chat(context("turn:1"), ROUTE, QUESTION)

    await monitor.marks.mark("billed", [(Home.EU, datetime.now(UTC))])

    assert await monitor.missing_now() == 1
    assert monitor.gauge() == 1
    assert await monitor.missing_now(Home.RU) == 0


async def test_a_stream_closed_before_its_usage_is_billed_without_a_row(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await chat_bench(homes, valkey)
    monitor = Monitor(homes, valkey)
    first = b'data: {"choices": [{"delta": {"content": "Hel"}, "finish_reason": null}]}\n\n'
    broken = b'data: {"error": {"message": "upstream reset"}}\n\n'
    bench.openrouter.answer("chat/completions", httpx.Response(200, content=first + broken))

    stream = bench.providers.stream_chat(context(), ROUTE, QUESTION)
    await anext(stream)
    with pytest.raises(AiCallError):
        await anext(stream)

    assert await monitor.missing_now() == 1


async def test_minute_rows_written_twice_or_doubled_in_a_batch_count_as_repeats(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = ai_bench(homes.transactions, doubles=Doubles(valkey=valkey))
    monitor = Monitor(homes, valkey)
    batch = [entry(Home.EU, f"stream:m:{minute}") for minute in range(3)]
    doubled = [*batch, entry(Home.EU, "stream:m:0")]
    replayed = [entry(Home.EU, row.effect_key) for row in batch]
    every = [*doubled, *replayed]
    await monitor.marks.mark("billed", [(row.home, row.created_at) for row in every])

    await bench.writer.record_many(doubled)
    await bench.writer.record_many(replayed)
    marks = await monitor.marks.of_hour(Home.EU, datetime.now(UTC))

    assert (marks.billed, marks.repeated) == (7, 4)
    assert await monitor.missing_now() == 0


async def test_an_hour_that_cannot_be_read_leaves_the_gauge_alone(homes: DatabaseAccess) -> None:
    monitor = Monitor(homes, unreachable_valkey())

    assert await monitor.missing_now() is None
    assert monitor.gauge() is None


def test_marks_fall_in_the_utc_hour_of_the_row() -> None:
    moment = datetime(2026, 10, 14, 13, 59, 59, tzinfo=UTC) + timedelta(hours=3)

    assert hour_of(moment.astimezone()) == datetime(2026, 10, 14, 16, tzinfo=UTC)
