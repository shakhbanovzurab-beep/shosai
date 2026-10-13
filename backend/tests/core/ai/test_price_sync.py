"""The daily OpenRouter price sync appends only prices that changed."""

from decimal import Decimal
from typing import Any

import httpx
import pytest

from shosai.core.ai.adapters.openrouter import OPENROUTER_API
from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.pricing.sync import listed_prices, price_sync_handler
from shosai.core.ai.results import Unit
from shosai.core.kernel.homes import Home
from shosai.core.tasks.payloads import HomeTaskPayload
from tests.core.ai.bench import set_prices
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
