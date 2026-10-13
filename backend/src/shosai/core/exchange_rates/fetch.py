"""The 6-hourly fetch of the Central Bank's daily rates into the EU home (ADR 0036).

The scheduler queues it as a periodic job of the EU home; one GET with a 10 s deadline, its
retry the next interval. Only the pairs the platform follows are stored, each as a new row.
A malformed answer stores nothing and is logged; it never writes a guess.
"""

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Final

import httpx
import structlog
from sqlalchemy import func, insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.exchange_rates.rates import CurrencyPair
from shosai.core.exchange_rates.records import ExchangeRate
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue

FETCH_DEADLINE: Final = timedelta(seconds=10)
CBR_CODES: Final = {"USD": CurrencyPair.USD_RUB, "EUR": CurrencyPair.EUR_RUB}
FETCH_RATES: Final = TaskDeclaration(
    name="exchange_rates.fetch",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=1),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
FETCH_RATES_JOB: Final = PeriodicJob(FETCH_RATES, timedelta(hours=6), homes=(Home.EU,))
log = structlog.stdlib.get_logger(__name__)


def parse_rates(document: object) -> dict[CurrencyPair, Decimal]:
    """The followed pairs of a `daily_json.js` answer: `Valute.<code>.Value / Nominal`."""
    valute = document.get("Valute") if isinstance(document, dict) else None
    if not isinstance(valute, dict):
        return {}
    rates: dict[CurrencyPair, Decimal] = {}
    for code, pair in CBR_CODES.items():
        entry = valute.get(code)
        if not isinstance(entry, dict):
            continue
        try:
            value = Decimal(str(entry.get("Value"))) / Decimal(str(entry.get("Nominal", 1)))
        except InvalidOperation, ZeroDivisionError:
            continue
        if value > 0:
            rates[pair] = value.quantize(Decimal("0.0001"))
    return rates


def rate_fetch_handler(
    transactions: HomeTransactions, client: httpx.AsyncClient, url: str
) -> TaskHandler[HomeTaskPayload]:
    """The fetch task bound to the process's HTTP client."""

    async def fetch(_payload: HomeTaskPayload) -> None:
        response = await client.get(url, timeout=FETCH_DEADLINE.total_seconds())
        response.raise_for_status()
        rates = parse_rates(response.json())
        if not rates:
            log.error("Ответ ЦБ без курсов: ничего не записано", status=response.status_code)
            return
        rows = [
            {"id": new_id(), "currency_pair": pair.value, "rate": rate, "source": "cbr",
             "fetched_at": func.now()}
            for pair, rate in rates.items()
        ]  # fmt: skip
        async with transactions.begin(TenancyScope(Home.EU)) as session:
            await session.execute(insert(ExchangeRate).values(rows))
        log.info("Курсы ЦБ записаны", pairs=sorted(pair.value for pair in rates))

    return TaskHandler(FETCH_RATES, fetch)
