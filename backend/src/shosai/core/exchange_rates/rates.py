"""The latest rate of a currency pair, cached 60 s per process (ADR 0036).

A cost row stores its rubles at the rate this port returns; with no rate yet the row keeps
its dollars only and is counted, never refused. A rate older than 3 days is a ticket alert
on `shosai_exchange_rate_age_seconds`.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Final

from prometheus_client import CollectorRegistry, Gauge
from sqlalchemy import func, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.exchange_rates.records import ExchangeRate
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope

RATES_TTL: Final = timedelta(seconds=60)


class CurrencyPair(StrEnum):
    """The pairs the platform follows."""

    USD_RUB = "USD/RUB"
    EUR_RUB = "EUR/RUB"


@dataclass(frozen=True, slots=True)
class Rate:
    """A rate and when it was fetched."""

    value: Decimal
    fetched_at: datetime


class ExchangeRates:
    """The read port of the latest rates; slices receive it by injection."""

    def __init__(
        self,
        transactions: HomeTransactions,
        registry: CollectorRegistry,
        ttl: timedelta = RATES_TTL,
    ) -> None:
        self._transactions = transactions
        self._ttl = ttl.total_seconds()
        self._cached: dict[CurrencyPair, tuple[Rate | None, float]] = {}
        self._age = Gauge(
            "shosai_exchange_rate_age_seconds",
            "Возраст последнего курса ЦБ, который видит процесс",
            ("pair",),
            registry=registry,
        )

    async def latest(self, pair: CurrencyPair) -> Rate | None:
        """The latest rate of the pair, or None before the first fetch."""
        cached = self._cached.get(pair)
        if cached is not None and time.monotonic() - cached[1] < self._ttl:
            return cached[0]
        statement = (
            select(ExchangeRate.rate, ExchangeRate.fetched_at, func.now())
            .where(ExchangeRate.currency_pair == pair.value)
            .order_by(ExchangeRate.fetched_at.desc())
            .limit(1)
        )
        async with self._transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
            row = (await session.execute(statement)).first()
        rate = None if row is None else Rate(value=row[0], fetched_at=row[1])
        if row is not None:
            self._age.labels(pair=pair.value).set((row[2] - row[1]).total_seconds())
        self._cached[pair] = (rate, time.monotonic())
        return rate
