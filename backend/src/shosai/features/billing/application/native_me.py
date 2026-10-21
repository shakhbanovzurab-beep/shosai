"""Billing's part of the native `GET /v1/auth/me`: `subscription`, `quota`, `features`.

The shapes are the draft's (`SubscriptionCardDTO`, `QuotaSnapshot`, `FeaturesOut`), read
by the shipped desktop clients. A person who never had a subscription gets no card, as
in the draft; the plan's tariff is derived from the catalogue (BL-D2): its price is the
bought period's in roubles, its period the draft's 31 or 366 days. Minutes come from the
month's usage, the month of the business calendar (ADR 0058); switches owned by other
slices (voice, live translation) keep the draft's defaults.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Final, Protocol
from uuid import UUID

from shosai.core.kernel.business_calendar import BusinessCalendar
from shosai.core.kernel.homes import Home
from shosai.features.billing.application.entitlement_entries import (
    EntitlementEntry,
    SubscriptionCard,
)
from shosai.features.billing.application.entitlement_snapshots import EntitlementSnapshots
from shosai.features.billing.domain.entitlements import days_left
from shosai.features.billing.domain.meters import SECONDS_IN_MINUTE, MinutesLeft
from shosai.features.billing.domain.money import Currency
from shosai.features.billing.domain.plans import BillingPeriod
from shosai.features.identity.contracts import Principal

# Сроки тарифов черновика в днях: клиенты показывают их как есть.
PERIOD_DAYS: Final = {BillingPeriod.MONTH: 31, BillingPeriod.YEAR: 366}
MINOR_IN_MAJOR: Final = 100
BYTES_IN_GB: Final = 1024**3


class MonthlyMinutes(Protocol):
    """Seconds of meetings a person recorded since a moment."""

    async def used_seconds(self, home: Home, user_id: UUID, since: datetime) -> int:
        """Recorded seconds from `since` on."""
        ...


class BillingMe:
    """The `identity.me_contribution` binding of billing."""

    def __init__(
        self,
        snapshots: EntitlementSnapshots,
        minutes: MonthlyMinutes,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        *,
        business: BusinessCalendar,
    ) -> None:
        self._snapshots = snapshots
        self._minutes = minutes
        self._clock = clock
        self._business = business

    async def native_me(self, principal: Principal) -> Mapping[str, object]:
        """The person's subscription card, minutes and plan switches."""
        now = self._clock()
        entry = await self._snapshots.entry(principal.home, principal.user_id)
        return {
            "subscription": None if entry.card is None else card_fields(entry.card, now),
            "quota": await self._quota(principal, entry, now),
            "features": feature_fields(entry),
        }

    async def _quota(
        self, principal: Principal, entry: EntitlementEntry, now: datetime
    ) -> dict[str, object]:
        limit = entry.snapshot.limits.meeting_minutes_per_month
        if limit is None:
            return {
                "unlimited": True, "limit_minutes": None, "bonus_minutes": 0,
                "used_minutes": None, "remaining_minutes": None, "exhausted": False,
            }  # fmt: skip
        start, _ = self._business.month_window(now)
        used = await self._minutes.used_seconds(principal.home, principal.user_id, start)
        left = MinutesLeft(limit, used)
        remaining = max(limit * SECONDS_IN_MINUTE - used, 0) / SECONDS_IN_MINUTE
        return {
            "unlimited": False, "limit_minutes": limit, "bonus_minutes": 0,
            "used_minutes": round(used / SECONDS_IN_MINUTE, 1),
            "remaining_minutes": round(remaining, 1), "exhausted": left.exhausted,
        }  # fmt: skip


def card_fields(card: SubscriptionCard, now: datetime) -> dict[str, object]:
    """`SubscriptionCardDTO` of the card."""
    running = card.expires_at is None or now < card.expires_at
    return {
        "status": "active" if running else "expired",
        "tariff": tariff_fields(card),
        "started_at": card.started_at,
        "expires_at": card.expires_at,
        "days_left": days_left(card.expires_at, now),
        "bonus_minutes": 0,
        "credits": 0.0,
    }


def tariff_fields(card: SubscriptionCard) -> dict[str, object]:
    """`TariffDTO` of the bought plan."""
    rub, usd, eur = (card.prices[currency] for currency in Currency)
    knowledge = card.knowledge_base_mb
    storage = None if card.file_manager_gb is None else card.file_manager_gb * BYTES_IN_GB
    return {
        "id": str(card.plan_id), "code": card.slug, "name": card.name,
        "price_rub": rub // MINOR_IN_MAJOR,
        "period_days": 0 if card.billing_period is None else PERIOD_DAYS[card.billing_period],
        "minutes_limit": card.minutes_limit,
        "allow_knowledge_base": knowledge is None or knowledge > 0,
        # Мультискриншот и режим System Design черновик давал на всех тарифах.
        "allow_multiscreenshot": True, "allow_system_design": True,
        "allow_frontier_models": card.frontier_models, "is_active": card.on_sale,
        "currency": "RUB", "price": rub / MINOR_IN_MAJOR,
        "price_eur": eur / MINOR_IN_MAJOR, "price_usd": usd / MINOR_IN_MAJOR,
        "storage_limit_bytes": storage,
    }  # fmt: skip


def feature_fields(entry: EntitlementEntry) -> dict[str, object]:
    """`FeaturesOut`: the teleprompter with any paid plan; the rest as the draft's defaults."""
    return {
        "voice_translation": False, "voice": False, "teleprompter": entry.snapshot.paid,
        "premium_weekly_remaining_pct": None, "premium_credit_usd": 0.0,
        "premium_credit_currency": "USD", "premium_credit_amount": 0.0,
    }  # fmt: skip
