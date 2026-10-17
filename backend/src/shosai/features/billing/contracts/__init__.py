"""What other slices may use of billing (billing plan §3.2, ADR 0054).

Every slice reads what a person or a workspace may use through `Entitlements`: a snapshot
of the plan in force, its limits and capabilities, cached and versioned, never guessed —
when it cannot be read the answer is `EntitlementsUnavailableError` (503, inv-3).
Usage is never in the snapshot: `MinutesAllowance` counts the month's minutes live. The
events billing publishes are in `contracts.events`.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import PortKey
from shosai.features.billing.domain.meters import MinutesLeft
from shosai.features.billing.domain.money import Currency
from shosai.features.billing.domain.plans import Audience, Capability, ModelTier, PlanLimits

__all__ = [
    "ENTITLEMENTS",
    "MINUTES_ALLOWANCE",
    "Audience",
    "Capability",
    "Currency",
    "EntitlementSnapshot",
    "EntitlementSource",
    "Entitlements",
    "EntitlementsUnavailableError",
    "MinutesAllowance",
    "MinutesLeft",
    "ModelTier",
    "PlanLimits",
]


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


class EntitlementsUnavailableError(Exception):
    """The snapshot could not be read; callers refuse (503), never assume a plan (inv-3)."""


class Entitlements(Protocol):
    """The plan in force of a person, from the cache or, on a miss, from their home."""

    async def snapshot(self, home: Home, user_id: UUID) -> EntitlementSnapshot:
        """The person's snapshot; raises `EntitlementsUnavailableError` when it cannot be read."""
        ...


class MinutesAllowance(Protocol):
    """The month's meeting minutes, counted live in the caller's transaction (BL-D3)."""

    async def check(self, session: AsyncSession, user_id: UUID, device: str | None) -> MinutesLeft:
        """Minutes left this month; a Free account on a device another one claimed gets none."""
        ...


ENTITLEMENTS: Final = PortKey[Entitlements]("billing.entitlements")
MINUTES_ALLOWANCE: Final = PortKey[MinutesAllowance]("billing.minutes_allowance")
