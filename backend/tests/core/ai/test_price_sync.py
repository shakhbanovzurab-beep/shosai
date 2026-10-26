"""The daily OpenRouter price sync appends only prices that changed."""

from decimal import Decimal
from typing import Any

import httpx
import pytest

from shosai.core.ai.adapters.openrouter import OPENROUTER_API
from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.pricing.sync import listed_prices, price_sync_handler
from shosai.core.ai.requests import ImageRequest
from shosai.core.ai.results import Unit
from shosai.core.kernel.homes import Home
from shosai.core.tasks.payloads import HomeTaskPayload
from tests.core.ai.bench import ai_bench, context, set_prices
from tests.doubles.openrouter import image_answer, usage
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot


def model(
    name: str, pricing: dict[str, Any], outputs: tuple[str, ...] = ("text",)
) -> dict[str, Any]:
    """One entry of OpenRouter's model list."""
    return {"id": name, "pricing": pricing, "architecture": {"output_modalities": list(outputs)}}


LISTING = {
    "data": [
        model("probe/chat", {"prompt": "0.000001", "completion": "0.000004",
                             "input_cache_read": "0.00000025", "web_search": "0.01"}),
        model("probe/voice", {"prompt": "0.000002", "completion": "0.000008",
                              "audio": "0.00004", "audio_output": "0.00008"}),
        model("probe/whisper", {"prompt": "0.0001", "completion": "0"}, ("transcription",)),
        model("probe/tokens-stt", {"prompt": "0.0000025", "completion": "0.00001"},
              ("transcription",)),
        model("probe/odd-stt", {"prompt": "0.1", "completion": "0"}, ("transcription",)),
        model("openrouter/auto", {"prompt": "-1", "completion": "-1"}),
        model("probe/long", {"prompt": "0.0000716666666667", "completion": "0"},
              ("transcription",)),
        model("probe/picture", {"prompt": "0.000005", "image": "0.02",
                                "image_token": "0.0000044", "image_output": "0.00003"},
              ("image",)),
    ]
}  # fmt: skip


def test_each_field_becomes_its_unit_and_unreadable_prices_are_skipped() -> None:
    listed = listed_prices(LISTING)

    assert listed == {
        ("probe/chat", Unit.INPUT): Decimal("0.000001000000"),
        ("probe/chat", Unit.OUTPUT): Decimal("0.000004000000"),
        ("probe/chat", Unit.CACHED_INPUT): Decimal("0.000000250000"),
        ("probe/voice", Unit.INPUT): Decimal("0.000002000000"),
        ("probe/voice", Unit.OUTPUT): Decimal("0.000008000000"),
        ("probe/voice", Unit.INPUT_AUDIO): Decimal("0.000040000000"),
        ("probe/voice", Unit.OUTPUT_AUDIO): Decimal("0.000080000000"),
        ("probe/whisper", Unit.AUDIO_SECOND): Decimal("0.000100000000"),
        ("probe/tokens-stt", Unit.INPUT): Decimal("0.000002500000"),
        ("probe/tokens-stt", Unit.OUTPUT): Decimal("0.000010000000"),
        ("probe/long", Unit.AUDIO_SECOND): Decimal("0.000071666667"),
        # Цена за поданную картинку (`image`) не пишется: единица `image` — за созданную.
        ("probe/picture", Unit.INPUT): Decimal("0.000005000000"),
        ("probe/picture", Unit.INPUT_IMAGE): Decimal("0.000004400000"),
        ("probe/picture", Unit.OUTPUT_IMAGE): Decimal("0.000030000000"),
    }


@pytest.mark.parametrize("document", [{}, {"data": "none"}, {"data": [{"id": 5}, "x"]}, []])
def test_a_list_without_readable_models_yields_nothing(document: object) -> None:
    assert listed_prices(document) == {}


def listing_client(answers: list[dict[str, Any]]) -> httpx.AsyncClient:
    """A client whose model list answers the given documents in turn."""

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/models"
        assert request.url.params["output_modalities"] == "all"
        return httpx.Response(200, json=answers.pop(0))

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


async def synced(run_slot: RunSlot) -> list[tuple[str, str, Decimal, str]]:
    """OpenRouter's price rows, oldest first."""
    rows = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT model, unit, price_usd, source FROM provider_prices "
        "WHERE provider = 'openrouter' AND model LIKE 'probe/%' ORDER BY created_at, model, unit",
    )
    return [(row["model"], row["unit"], row["price_usd"], row["source"]) for row in rows]


async def test_a_sync_appends_only_new_and_changed_prices(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await set_prices(
        homes.transactions, ModelRef(Provider.OPENROUTER, "probe/chat"), input_token="0.000001"
    )
    first = {"data": [model("probe/chat", {"prompt": "0.000001", "completion": "0.000004"})]}
    same = {"data": [model("probe/chat", {"prompt": "0.000001", "completion": "0.000004"})]}
    cheaper = {"data": [model("probe/chat", {"prompt": "0.0000008", "completion": "0.000004"})]}
    sync = price_sync_handler(
        homes.transactions, listing_client([first, same, cheaper]), OPENROUTER_API
    )

    for _ in range(3):
        await sync.handle(HomeTaskPayload(home=Home.EU))

    assert await synced(run_slot) == [
        ("probe/chat", "input_token", Decimal("0.000001000000"), "operator"),
        ("probe/chat", "output_token", Decimal("0.000004000000"), "openrouter"),
        ("probe/chat", "input_token", Decimal("0.000000800000"), "openrouter"),
    ]


async def test_a_failed_listing_writes_nothing(homes: DatabaseAccess, run_slot: RunSlot) -> None:
    sync = price_sync_handler(homes.transactions, listing_client([{"data": []}]), OPENROUTER_API)

    await sync.handle(HomeTaskPayload(home=Home.EU))

    assert await synced(run_slot) == []


PICTURE = ModelRoute(ModelRef(Provider.OPENROUTER, "probe/picture"))
PNG = b"\x89PNG\r\n\x1a\n"


async def test_a_picture_priced_by_image_tokens_is_made_after_the_sync(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = ai_bench(homes.transactions)
    refused = None
    try:
        await bench.providers.generate_image(context("picture:0"), PICTURE, ImageRequest("a study"))
    except AiCallError as error:
        refused = error.failure
    priced = {"prompt": "0.000005", "image_token": "0.0000044", "image_output": "0.00003"}
    listing = {"data": [model("probe/picture", priced, ("image",))]}
    await price_sync_handler(homes.transactions, listing_client([listing])).handle(
        HomeTaskPayload(home=Home.EU)
    )
    used = usage(12, 1_300) | {"completion_tokens_details": {"image_tokens": 1_290}}
    # Новый процесс: прежний помнит «цен нет» до конца срока своего кэша цен.
    bench = ai_bench(homes.transactions)
    bench.openrouter.answer("chat/completions", image_answer(PNG, "image/png", used))

    made = await bench.providers.generate_image(
        context("picture:1"), PICTURE, ImageRequest("a quiet study")
    )

    [row] = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT output_tokens, output_image_tokens, unit, units, cost_usd, cost_source"
        " FROM provider_costs WHERE effect_key = 'picture:1'",
    )
    assert refused is AiFailure.MODEL_UNPRICED
    assert (made.data, made.usage.output_image_tokens) == (PNG, 1_290)
    # Без цены от провайдера: 12 входных токенов, 10 текстовых выходных по цене входных
    # (своей нет) и 1 290 токенов картинки по 0,00003.
    assert (row["output_tokens"], row["output_image_tokens"], row["unit"]) == (10, 1_290, "image")
    assert row["cost_source"] == "priced"
    assert row["cost_usd"] == Decimal("0.000060") + Decimal("0.0387")
