"""Every attempt sent to a provider is counted, timed and traced, without a word of content."""

import httpx
import pytest
from opentelemetry.trace import StatusCode
from redis.asyncio import Redis

from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from tests.core.ai.bench import CHAT_MODEL, ROUTE, AiBench, Doubles, ai_bench, context, set_prices
from tests.doubles.openrouter import chat_answer, stream_answer, usage
from tests.harness.database_access import DatabaseAccess

QUESTION = ChatRequest(
    messages=(ChatMessage(Role.USER, (TextPart("Where is Anna's contract?"),)),),
    max_output_tokens=20,
)
ANSWER = "In the shared folder."
CALL = {"provider": "openrouter", "kind": "chat", "call_class": "standard"}


async def bench_of(homes: DatabaseAccess, valkey: Redis) -> AiBench:
    """A priced chat model over the run's Valkey."""
    await set_prices(
        homes.transactions, CHAT_MODEL, input_token="0.000001", output_token="0.000004"
    )
    return ai_bench(homes.transactions, doubles=Doubles(valkey=valkey))


def calls(bench: AiBench, outcome: str) -> float:
    """Attempts of the probe chat with the outcome."""
    return bench.sample("shosai_ai_calls_total", **CALL, outcome=outcome)


async def test_an_answered_call_is_counted_timed_and_traced_without_content(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await bench_of(homes, valkey)
    bench.openrouter.answer("chat/completions", chat_answer(ANSWER, usage(10, 2, cost=0.001)))

    await bench.providers.chat(context(), ROUTE, QUESTION)
    [span] = bench.spans.get_finished_spans()

    assert calls(bench, "ok") == 1
    assert bench.sample("shosai_ai_call_duration_seconds_count", **CALL, outcome="ok") == 1
    assert span.name == "ai.call"
    assert dict(span.attributes or {}) == {
        "ai.provider": "openrouter",
        "ai.model": "probe/chat",
        "ai.kind": "chat",
        "ai.call_class": "standard",
        "ai.outcome": "ok",
    }
    assert not span.events


async def test_a_provider_failure_is_its_code_on_the_metric_and_an_error_on_the_span(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await bench_of(homes, valkey)
    failure = httpx.Response(500, json={"error": {"message": f"Failed on: {ANSWER}"}})
    bench.openrouter.answer("chat/completions", failure)

    with pytest.raises(AiCallError):
        await bench.providers.chat(context(), ROUTE, QUESTION)
    [span] = bench.spans.get_finished_spans()

    assert calls(bench, "provider_error") == 1
    assert span.status.status_code is StatusCode.ERROR
    assert (span.attributes or {})["error.type"] == "provider_error"
    assert ANSWER not in str(span.to_json())


async def test_a_stream_reports_its_first_piece_and_ends_with_its_outcome(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await bench_of(homes, valkey)
    bench.openrouter.answer(
        "chat/completions", stream_answer(["In the ", "shared folder."], usage(10, 2, cost=0.001))
    )

    pieces = [delta.text async for delta in bench.providers.stream_chat(context(), ROUTE, QUESTION)]

    assert "".join(pieces) == ANSWER
    assert (
        bench.sample(
            "shosai_ai_time_to_first_piece_seconds_count", provider="openrouter", kind="chat"
        )
        == 1
    )
    assert calls(bench, "ok") == 1
    assert [span.attributes["ai.outcome"] for span in bench.spans.get_finished_spans()
            if span.attributes] == ["ok"]  # fmt: skip


async def test_a_stream_the_caller_left_ends_interrupted(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await bench_of(homes, valkey)
    bench.openrouter.answer(
        "chat/completions", stream_answer(["In the ", "shared folder."], usage(10, 2, cost=0.001))
    )

    stream = bench.providers.stream_chat(context(), ROUTE, QUESTION)
    await anext(stream)
    await stream.aclose()

    assert calls(bench, "interrupted") == 1
    assert calls(bench, "ok") == 0
