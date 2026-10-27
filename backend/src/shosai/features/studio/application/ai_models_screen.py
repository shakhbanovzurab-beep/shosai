"""What Admin > AI models shows (studio plan §3.5, SLICE_MAP §4.2.19, ADR 0074).

The screen shows the catalogue, each model with its prices per million tokens from F6's price
list and its spend and requests this business month. It shows the month's spend, forecast and
tokens, the last thirty days and today. Spend on models outside the catalogue — transcription,
documents, Jev, embeddings — is apart, so the shares add up. It shows the OpenRouter key's
state and balance and the defaults of every role. Every part is read at once, none waits for
another. The connection check asks OpenRouter's balance now and times the answer.
"""

import asyncio
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final

import structlog
from pydantic import SecretStr
from sqlalchemy import select

from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.listing import ModelListing
from shosai.core.ai.results import Unit
from shosai.core.ai.spend.reports import ReportPeriod, SpendReports, SummaryGroup, SummaryRow
from shosai.core.ai.spend.standing import Credits, OpenRouterCredits
from shosai.core.db.transactions import HomeTransactions
from shosai.features.studio.application.catalogue_admin import EU
from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.defaults import RoleDefault
from shosai.features.studio.infrastructure.catalogue_store import default_of, model_of
from shosai.features.studio.infrastructure.platform_records import (
    CatalogueRecord,
    RoleDefaultRecord,
)

PER_MILLION: Final = Decimal(1_000_000)
ZERO: Final = Decimal(0)
HINT_CHARACTERS: Final = 4
UNREACHABLE: Final = "openrouter_unreachable"
NO_MANAGEMENT_KEY: Final = "management_key_missing"
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ModelRow:
    """A catalogue model with its prices and this month's use."""

    model: CatalogueModel
    price_input_per_m: Decimal | None
    price_output_per_m: Decimal | None
    month_spend: Decimal
    month_requests: int


@dataclass(frozen=True, slots=True)
class Spend:
    """The platform's AI spend, USD, by the business calendar."""

    today: Decimal
    month: Decimal
    forecast_month: Decimal
    tokens_in_month: int
    tokens_out_month: int
    requests_month: int
    outside_spend: Decimal
    outside_requests: int
    daily: tuple[tuple[date, Decimal], ...]


@dataclass(frozen=True, slots=True)
class KeyState:
    """The OpenRouter key and balance as the screen shows them."""

    configured: bool
    hint: str | None
    credits: Credits | None
    sync_error: str | None


@dataclass(frozen=True, slots=True)
class Screen:
    """Everything the screen loads in one answer."""

    provider: KeyState
    spend: Spend
    models: tuple[ModelRow, ...]
    defaults: tuple[RoleDefault, ...]


@dataclass(frozen=True, slots=True)
class ConnectionCheck:
    """The connection check's answer."""

    ok: bool
    latency_ms: int | None
    code: str | None
    checked_at: datetime
    provider: KeyState


def key_hint(key: SecretStr | None) -> str | None:
    """The key's last characters, never the key."""
    if key is None:
        return None
    value = key.get_secret_value()
    return "…" + value[-HINT_CHARACTERS:] if len(value) > 2 * HINT_CHARACTERS else "…"


def by_model(rows: Sequence[SummaryRow]) -> Mapping[str, SummaryRow]:
    """The month's summary rows by OpenRouter model id."""
    return {row.key: row for row in rows}


class AiModelsScreen:
    """Reads the AI models screen and checks the connection."""

    def __init__(
        self,
        transactions: HomeTransactions,
        sources: tuple[SpendReports, OpenRouterCredits, ModelListing],
        key: SecretStr | None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._reports, self._credits, self._listing = sources
        self._key = key
        self._clock = clock

    async def screen(self) -> Screen:
        """The screen's answer, its parts read at once."""
        at = self._clock()
        reports = self._reports
        catalogue, summary, daily, forecast, totals, provider = await asyncio.gather(
            self._catalogue(),
            reports.summary(SummaryGroup.MODEL, ReportPeriod.MONTH, at),
            reports.daily(at),
            reports.forecast(at),
            reports.month_totals(at),
            self.key_state(),
        )
        models, defaults = catalogue
        month = by_model(summary)
        rows = tuple([await self._row(model, month) for model in models])
        listed = {model.openrouter_id for model in models}
        outside = [row for key, row in month.items() if key not in listed]
        days = dict.fromkeys(reports.days(at), ZERO)
        for row in daily:
            days[row.day] = days.get(row.day, ZERO) + row.cost_usd
        spend = Spend(
            today=days[reports.days(at)[-1]],
            month=sum((row.cost_usd for row in summary), ZERO),
            forecast_month=forecast.projected_usd,
            tokens_in_month=totals.input_tokens,
            tokens_out_month=totals.output_tokens,
            requests_month=totals.calls,
            outside_spend=sum((row.cost_usd for row in outside), ZERO),
            outside_requests=sum(row.calls for row in outside),
            daily=tuple(days.items()),
        )
        return Screen(provider, spend, rows, defaults)

    async def row(self, model: CatalogueModel) -> ModelRow:
        """One model's row, after a change to it."""
        at = self._clock()
        summary = await self._reports.summary(SummaryGroup.MODEL, ReportPeriod.MONTH, at)
        return await self._row(model, by_model(summary))

    async def key_state(self, *, fresh: bool = False) -> KeyState:
        """The key and the balance; a balance OpenRouter does not give is an error code."""
        configured, hint = self._key is not None, key_hint(self._key)
        try:
            credits = await self._credits.credits(fresh=fresh)
        except AiCallError as error:
            log.warning("Баланс OpenRouter не прочитан", failure=error.failure.value)
            return KeyState(configured, hint, None, UNREACHABLE)
        return KeyState(configured, hint, credits, None)

    async def check(self) -> ConnectionCheck:
        """Ask OpenRouter's balance now and time it."""
        started = time.monotonic()
        provider = await self.key_state(fresh=True)
        latency = round((time.monotonic() - started) * 1000)
        checked_at = self._clock()
        if provider.sync_error is not None:
            return ConnectionCheck(
                ok=False,
                latency_ms=None,
                code=provider.sync_error,
                checked_at=checked_at,
                provider=provider,
            )
        if provider.credits is None:
            return ConnectionCheck(
                ok=False,
                latency_ms=None,
                code=NO_MANAGEMENT_KEY,
                checked_at=checked_at,
                provider=provider,
            )
        return ConnectionCheck(
            ok=True, latency_ms=latency, code=None, checked_at=checked_at, provider=provider
        )

    async def _catalogue(self) -> tuple[tuple[CatalogueModel, ...], tuple[RoleDefault, ...]]:
        async with self._transactions.begin(EU, read_only=True) as session:
            rows = await session.scalars(
                select(CatalogueRecord)
                .where(CatalogueRecord.retired_at.is_(None))
                .order_by(CatalogueRecord.maker, CatalogueRecord.name)
            )
            models = tuple(model_of(row) for row in rows)
            defaults = await session.scalars(
                select(RoleDefaultRecord).order_by(RoleDefaultRecord.role)
            )
            return models, tuple(default_of(row) for row in defaults)

    async def _row(self, model: CatalogueModel, month: Mapping[str, SummaryRow]) -> ModelRow:
        prices = await self._listing.prices.prices_of(
            ModelRef(Provider.OPENROUTER, model.openrouter_id)
        )
        used = month.get(model.openrouter_id)
        price_in, price_out = prices.get(Unit.INPUT), prices.get(Unit.OUTPUT)
        return ModelRow(
            model=model,
            price_input_per_m=None if price_in is None else price_in * PER_MILLION,
            price_output_per_m=None if price_out is None else price_out * PER_MILLION,
            month_spend=used.cost_usd if used is not None else ZERO,
            month_requests=used.calls if used is not None else 0,
        )
