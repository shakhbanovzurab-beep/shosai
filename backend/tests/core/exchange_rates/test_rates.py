"""The Central Bank's rates: parsed strictly, stored in the EU home, read cached (ADR 0036)."""

from decimal import Decimal

import httpx
import pytest
from prometheus_client import CollectorRegistry

from shosai.core.exchange_rates.fetch import parse_rates, rate_fetch_handler
from shosai.core.exchange_rates.rates import CurrencyPair, ExchangeRates
from shosai.core.kernel.homes import Home
from shosai.core.tasks.payloads import HomeTaskPayload
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

CBR_URL = "https://cbr.test/daily_json.js"
DAILY = {
    "Date": "2026-10-13T11:30:00+03:00",
    "Valute": {
        "USD": {"CharCode": "USD", "Nominal": 1, "Value": 92.4512},
        "EUR": {"CharCode": "EUR", "Nominal": 1, "Value": 100.1234},
        "JPY": {"CharCode": "JPY", "Nominal": 100, "Value": 61.5},
    },
}


def cbr(answer: httpx.Response) -> httpx.AsyncClient:
    """An HTTP client whose every request gets the answer."""
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: answer))


def test_only_the_followed_pairs_are_read_per_one_unit() -> None:
    weird = {"Valute": {"USD": {"Nominal": 10, "Value": 924.5}, "EUR": {"Value": "x"}}}

    assert parse_rates(DAILY) == {
        CurrencyPair.USD_RUB: Decimal("92.4512"),
        CurrencyPair.EUR_RUB: Decimal("100.1234"),
    }
    assert parse_rates(weird) == {CurrencyPair.USD_RUB: Decimal("92.4500")}


@pytest.mark.parametrize("document", [None, [], {"Valute": []}, {"Valute": {"USD": {"Value": -1}}}])
def test_an_answer_without_rates_gives_none(document: object) -> None:
    assert parse_rates(document) == {}


async def test_the_fetch_stores_both_pairs_and_the_port_reads_the_latest(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    fetch = rate_fetch_handler(homes.transactions, cbr(httpx.Response(200, json=DAILY)), CBR_URL)
    rates = ExchangeRates(homes.transactions, CollectorRegistry())
    before = await rates.latest(CurrencyPair.USD_RUB)

    await fetch.handle(HomeTaskPayload(home=Home.EU))

    stored = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT currency_pair, rate, source FROM exchange_rates ORDER BY currency_pair",
    )
    assert before is None
    assert [(row["currency_pair"], row["rate"], row["source"]) for row in stored] == [
        ("EUR/RUB", Decimal("100.1234"), "cbr"),
        ("USD/RUB", Decimal("92.4512"), "cbr"),
    ]
    fresh = ExchangeRates(homes.transactions, CollectorRegistry())
    latest = await fresh.latest(CurrencyPair.USD_RUB)
    assert latest is not None
    assert latest.value == Decimal("92.4512")


async def test_a_failed_or_empty_answer_stores_nothing(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    empty = rate_fetch_handler(homes.transactions, cbr(httpx.Response(200, json={})), CBR_URL)
    down = rate_fetch_handler(homes.transactions, cbr(httpx.Response(503)), CBR_URL)

    await empty.handle(HomeTaskPayload(home=Home.EU))
    with pytest.raises(httpx.HTTPStatusError):
        await down.handle(HomeTaskPayload(home=Home.EU))

    rows = await fetch_rows(run_slot.claimed.connections[Home.EU], "SELECT id FROM exchange_rates")
    assert rows == []
