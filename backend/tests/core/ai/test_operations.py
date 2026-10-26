"""Streaming, embeddings, images and failures through the port, against the scripted OpenRouter."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

import httpx
import pytest

from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import (
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    ImagePart,
    ImageRequest,
    Role,
    TextPart,
    ToolSchema,
)
from shosai.core.kernel.homes import Home
from tests.core.ai.bench import CHAT_MODEL, ROUTE, AiBench, Doubles, ai_bench, context, set_prices
from tests.doubles.openrouter import (
    chat_answer,
    embeddings_answer,
    image_answer,
    stream_answer,
    usage,
)
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

PICTURE = b"\x89PNG\r\n\x1a\nprobe"
QUESTION = ChatRequest(
    messages=(
        ChatMessage(Role.SYSTEM, (TextPart("Answer briefly."),)),
        ChatMessage(Role.USER, (TextPart("What is on it?"), ImagePart(PICTURE, "image/png"))),
    ),
    max_output_tokens=50,
    tools=(ToolSchema("search_notes", "Search the user's notes.", {"type": "object"}),),
    web_search_results=3,
)


async def priced_bench(homes: DatabaseAccess) -> AiBench:
    """A bench whose probe model has every price."""
    await set_prices(
        homes.transactions, CHAT_MODEL, input_token="0.000001", output_token="0.000002",
        request="0.001", image="0.04",
    )  # fmt: skip
    return ai_bench(homes.transactions)


async def rows(run_slot: RunSlot) -> int:
    """Cost rows of the EU home."""
    count = await fetch_value(
        run_slot.claimed.connections[Home.EU], "SELECT count(*) FROM provider_costs"
    )
    assert isinstance(count, int)
    return count


async def test_a_request_carries_images_tools_and_web_search(homes: DatabaseAccess) -> None:
    bench = await priced_bench(homes)
    bench.openrouter.answer("chat/completions", chat_answer("A chart.", usage(50, 5, cost=0.0002)))

    await bench.providers.chat(context(), ROUTE, QUESTION)

    [body] = bench.openrouter.bodies("chat/completions")
    image = body["messages"][1]["content"][1]
    assert image["type"] == "image_url"
    assert image["image_url"]["url"].startswith("data:image/png;base64,")
    assert [tool["type"] for tool in body["tools"]] == ["function", "openrouter:web_search"]
    assert body["tools"][1]["parameters"] == {
        "engine": "exa", "max_results": 3, "max_total_results": 3,
    }  # fmt: skip
    assert (body["model"], body["max_tokens"], body["stream"]) == ("probe/chat", 50, False)


async def test_a_web_answer_brings_the_pages_it_cites(homes: DatabaseAccess) -> None:
    bench = await priced_bench(homes)
    page = {"url": "https://news.example/launch", "title": "Launch", "content": "In May."}
    bench.openrouter.answer(
        "chat/completions",
        chat_answer(
            "It moved to May.", usage(900, 20, cost=0.0213),
            annotations=[{"type": "url_citation", "url_citation": page}],
        ),
    )  # fmt: skip

    answer = await bench.providers.chat(context(), ROUTE, QUESTION)

    assert [(c.url, c.title, c.snippet) for c in answer.citations] == [
        ("https://news.example/launch", "Launch", "In May.")
    ]
    assert answer.usage.reported_cost_usd is not None


async def test_a_stream_records_its_cost_once_when_the_usage_arrives(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await priced_bench(homes)
    bench.openrouter.answer(
        "chat/completions", stream_answer(["Hel", "lo"], usage(9, 2, cost=0.0003))
    )

    deltas = [delta async for delta in bench.providers.stream_chat(context(), ROUTE, QUESTION)]

    assert "".join(delta.text for delta in deltas) == "Hello"
    assert deltas[-1].usage is not None
    assert await rows(run_slot) == 1


async def test_a_stream_closed_before_its_usage_is_counted_as_a_lost_cost(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await priced_bench(homes)
    bench.openrouter.answer(
        "chat/completions", stream_answer(["Hel", "lo"], usage(9, 2, cost=0.0003))
    )

    stream = bench.providers.stream_chat(context(), ROUTE, QUESTION)
    first = await anext(stream)
    await stream.aclose()

    assert first.text == "Hel"
    assert await rows(run_slot) == 0
    assert bench.sample("shosai_ai_calls_without_cost_row_total") == 1


async def test_embeddings_come_back_in_the_order_of_the_texts(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await priced_bench(homes)
    bench.openrouter.answer(
        "embeddings", embeddings_answer([[0.1, 0.2], [0.3, 0.4]], usage(8, cost=0.00001))
    )

    result = await bench.providers.embed(context(), ROUTE, EmbeddingRequest(("one", "two")))

    assert result.vectors == ((0.1, 0.2), (0.3, 0.4))
    assert await rows(run_slot) == 1


async def test_an_image_comes_back_as_bytes_of_an_image_type(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await priced_bench(homes)
    bench.openrouter.answer(
        "chat/completions", image_answer(PICTURE, "image/png", usage(20, cost=0.04))
    )

    image = await bench.providers.generate_image(context(), ROUTE, ImageRequest("a quiet study"))

    [body] = bench.openrouter.bodies("chat/completions")
    assert (image.data, image.media_type) == (PICTURE, "image/png")
    assert body["modalities"] == ["image"]
    assert await rows(run_slot) == 1


@dataclass(frozen=True)
class Refusal:
    """A provider's error answer, what the caller sees, and how many times it was sent."""

    status: int
    text: str
    failure: AiFailure
    sent: int


@pytest.mark.parametrize(
    "refusal",
    [
        Refusal(429, "Rate limit exceeded", AiFailure.RATE_LIMITED, 2),
        Refusal(
            400,
            "This model's maximum context length is 8192 tokens",
            AiFailure.CONTEXT_LENGTH_EXCEEDED,
            1,
        ),
        Refusal(403, "Input was flagged by moderation", AiFailure.CONTENT_REFUSED, 1),
        Refusal(404, "No endpoints found", AiFailure.MODEL_UNAVAILABLE, 1),
        Refusal(500, "Internal error", AiFailure.PROVIDER_ERROR, 1),
        Refusal(502, "Bad gateway", AiFailure.PROVIDER_ERROR, 2),
    ],
)
async def test_a_failed_call_says_why_is_retried_only_before_an_answer_and_writes_no_row(
    homes: DatabaseAccess, run_slot: RunSlot, refusal: Refusal
) -> None:
    bench = await priced_bench(homes)
    answer = {"error": {"message": refusal.text}}
    for _ in range(2):
        bench.openrouter.answer("chat/completions", httpx.Response(refusal.status, json=answer))

    with pytest.raises(AiCallError) as raised:
        await bench.providers.chat(context(), ROUTE, QUESTION)

    assert raised.value.failure is refusal.failure
    # 429, 502, 503 и 504 пришли без ответа: запрос повторён один раз (F6-C15).
    assert len(bench.openrouter.bodies("chat/completions")) == refusal.sent
    assert await rows(run_slot) == 0


async def test_a_call_past_its_deadline_is_cut_and_writes_no_row(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await priced_bench(homes)
    slow = httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1/",
        transport=httpx.MockTransport(SlowAnswers(seconds=1.0).handle),
    )
    bench = ai_bench(homes.transactions, doubles=Doubles(openrouter=slow))

    with pytest.raises(AiCallError) as raised:
        await bench.providers.chat(context(deadline=timedelta(milliseconds=50)), ROUTE, QUESTION)

    assert raised.value.failure is AiFailure.DEADLINE_EXCEEDED
    assert await rows(run_slot) == 0


class SlowAnswers:
    """A provider that answers only after a delay."""

    def __init__(self, seconds: float) -> None:
        self._seconds = seconds

    async def handle(self, _request: httpx.Request) -> httpx.Response:
        """Wait, then answer."""
        await asyncio.sleep(self._seconds)
        return chat_answer("late", usage(1, 1, cost=0.0))
