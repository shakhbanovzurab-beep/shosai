"""What other slices may use of billing (billing plan §3.2, ADR 0054).

Every slice reads what a person or a workspace may use through `Entitlements`: a snapshot
of the plan in force, its limits and capabilities, cached and versioned, never guessed —
when it cannot be read the answer is `EntitlementsUnavailableError` (503, inv-3).
Usage is never in the snapshot: `MinutesAllowance` counts the month's minutes live, from
the live meetings meetings report (`MEETING_MINUTES`, bound by notes; none until then)
and the tombstones of deleted ones (`UsageTombstones`). `TokenAllowanceReader` tells the
agent, before a model request, where its tokens come from: the week's allowance, packs, a
fall back to a standard model, or a stop with the limit that stopped it (BL-D4). `CommerceFacts`
gives the platform operator's Leo the catalogue's plans and promo codes (agent AG-D5). The
events billing publishes are in `contracts.events`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import PortKey
from shosai.features.billing.domain.meters import (
    MinutesLeft,
    TokenDecision,
    TokenLimit,
    TokenRoute,
)
from shosai.features.billing.domain.money import Currency
from shosai.features.billing.domain.plans import Audience, Capability, ModelTier, PlanLimits

__all__ = [
    "COMMERCE_FACTS",
    "ENTITLEMENTS",
    "MEETING_MINUTES",
    "MINUTES_ALLOWANCE",
    "TOKEN_ALLOWANCE",
    "USAGE_TOMBSTONES",
    "Audience",
    "Capability",
    "CommerceFacts",
    "Currency",
    "EntitlementSnapshot",
    "EntitlementSource",
    "Entitlements",
    "EntitlementsUnavailableError",
    "FreeDeviceTakenError",
    "MeetingMinutes",
    "MinutesAllowance",
    "MinutesExhaustedError",
    "MinutesLeft",
    "ModelTier",
    "PlanLimits",
    "PlanSummary",
    "PromoSummary",
    "TokenAllowanceReader",
    "TokenDecision",
    "TokenLimit",
    "TokenRoute",
    "UploadExceedsMinutesError",
    "UsageTombstones",
]


# Через сколько клиенту повторить запрос, когда права не прочитаны.
RETRY_AFTER_SECONDS: Final = 5


class EntitlementSource(StrEnum):
    """Where the plan in force comes from."""

    PERSONAL = "personal"
    # Место в пространстве на командном тарифе перекрывает личный тариф.
    WORKSPACE_SEAT = "workspace_seat"


@dataclass(frozen=True, slots=True)
class EntitlementSnapshot:
    """What a person may use now: the plan in force, its limits and capabilities."""

    user_id: UUID
    plan_slug: str
    plan_name: str
    audience: Audience
    paid: bool
    in_grace: bool
    paid_until: datetime | None
    limits: PlanLimits
    capabilities: frozenset[Capability]
    source: EntitlementSource
    workspace_id: UUID | None
    # Растёт с каждым изменением подписки: кеш со старой версией не читается.
    version: int


class EntitlementsUnavailableError(AppError):
    """The snapshot could not be read; callers refuse (503), never assume a plan (inv-3)."""

    def __init__(self) -> None:
        super().__init__(
            "entitlements_unavailable",
            HTTPStatus.SERVICE_UNAVAILABLE,
            params={"retry_after_seconds": RETRY_AFTER_SECONDS},
        )


class Entitlements(Protocol):
    """The plan in force of a person, from the cache or, on a miss, from their home."""

    async def snapshot(self, home: Home, user_id: UUID) -> EntitlementSnapshot:
        """The person's snapshot; raises `EntitlementsUnavailableError` when it cannot be read."""
        ...


class MinutesExhaustedError(AppError):
    """The month's minutes are used up: a meeting does not start (402)."""

    def __init__(self, limit_minutes: int) -> None:
        super().__init__(
            "minutes_exhausted",
            HTTPStatus.PAYMENT_REQUIRED,
            params={"limit_minutes": limit_minutes},
        )


class UploadExceedsMinutesError(AppError):
    """A recording is longer than the minutes left: it is not processed (402, BL-D3)."""

    def __init__(self, remaining_minutes: int) -> None:
        super().__init__(
            "upload_exceeds_minutes",
            HTTPStatus.PAYMENT_REQUIRED,
            params={"remaining_minutes": remaining_minutes},
        )


class FreeDeviceTakenError(AppError):
    """Another Free account already uses this desktop device (403, BL-D3)."""

    def __init__(self) -> None:
        super().__init__("free_plan_device_taken", HTTPStatus.FORBIDDEN)


class MinutesAllowance(Protocol):
    """The month's meeting minutes, counted live in the caller's transaction (BL-D3).

    The caller's transaction is the person's, in their home; `check` writes a Free
    account's device claim in it, so it is a writing transaction.
    """

    async def check(self, session: AsyncSession, user_id: UUID, device: str | None) -> MinutesLeft:
        """Minutes left this month; raises `MinutesExhaustedError` at the limit and
        `FreeDeviceTakenError` for a Free account on a device another Free account claimed."""
        ...

    async def covers(self, session: AsyncSession, user_id: UUID, seconds: int) -> MinutesLeft:
        """Minutes left when a recording this long fits them; `UploadExceedsMinutesError` if not."""
        ...


class UsageTombstones(Protocol):
    """The minutes of a deleted meeting, kept in the month it happened (ADR 0007)."""

    async def meeting_deleted(
        self, session: AsyncSession, user_id: UUID, meeting: tuple[UUID, datetime], seconds: int
    ) -> None:
        """Record `(meeting id, start)` with its seconds in the caller's deleting transaction.

        A repeat records nothing more; a meeting older than the previous month is not counted
        any more and leaves no tombstone.
        """
        ...


class MeetingMinutes(Protocol):
    """Seconds of the person's meetings that still exist, by their start (bound by notes)."""

    async def recorded_seconds(
        self, session: AsyncSession, user_id: UUID, window: tuple[datetime, datetime]
    ) -> int:
        """Seconds of meetings started in `[start, end)`, read in the caller's transaction."""
        ...


@dataclass(frozen=True, slots=True)
class PlanSummary:
    """A plan of the catalogue as the operator's Leo reads it: its prices in minor units."""

    slug: str
    name: str
    audience: str
    subscribers: int
    on_sale: bool
    archived: bool
    month_prices: Mapping[str, int]
    year_prices: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class PromoSummary:
    """A promo code as the operator's Leo reads it, with its status today."""

    code: str
    status: str
    percent_off: int | None
    redemptions: int
    max_redemptions: int | None
    valid_until: date | None


class CommerceFacts(Protocol):
    """The catalogue's plans and promo codes, for the platform operator (agent AG-D5)."""

    async def plans(self) -> Sequence[PlanSummary]:
        """Every plan, archived ones included, in the pricing page's order."""
        ...

    async def promo_codes(self) -> Sequence[PromoSummary]:
        """Every promo code with its status today."""
        ...


class TokenAllowanceReader(Protocol):
    """The route of a person's next model request of a tier, read live (never cached)."""

    async def decision(self, home: Home, user_id: UUID, tier: ModelTier) -> TokenDecision:
        """Within the allowance, from packs, fall back or stop with its reason; raises
        `EntitlementsUnavailableError` when it cannot be read."""
        ...


ENTITLEMENTS: Final = PortKey[Entitlements]("billing.entitlements")
MINUTES_ALLOWANCE: Final = PortKey[MinutesAllowance]("billing.minutes_allowance")
TOKEN_ALLOWANCE: Final = PortKey[TokenAllowanceReader]("billing.token_allowance")
COMMERCE_FACTS: Final = PortKey[CommerceFacts]("billing.commerce_facts")
USAGE_TOMBSTONES: Final = PortKey[UsageTombstones]("billing.usage_tombstones")
# Привязывает meetings; пока его нет, порт пуст и живых минут ноль.
MEETING_MINUTES: Final = PortKey[MeetingMinutes]("billing.meeting_minutes")
