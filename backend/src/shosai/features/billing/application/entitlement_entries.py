"""What billing keeps of a person's entitlements between reads: the snapshot and the card.

An entry is built from the person's subscription in their home and the EU catalogue. It
holds until `valid_until` — the next moment the plan in force changes by time alone —
and only for the catalogue it was built from (`catalogue`) and its subscription version.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shosai.features.billing.contracts import EntitlementSnapshot
from shosai.features.billing.domain.money import Currency
from shosai.features.billing.domain.plans import BillingPeriod


@dataclass(frozen=True, slots=True)
class SubscriptionCard:
    """The person's subscription as the native clients show it: the plan bought and its dates."""

    plan_id: UUID
    slug: str
    name: str
    # Цены купленного периода (месячные, когда период не задан), в минорных единицах.
    prices: Mapping[Currency, int]
    billing_period: BillingPeriod | None
    minutes_limit: int | None
    knowledge_base_mb: int | None
    file_manager_gb: int | None
    frontier_models: bool
    on_sale: bool
    started_at: datetime
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class EntitlementEntry:
    """A snapshot, the card, and what it was built from."""

    snapshot: EntitlementSnapshot
    card: SubscriptionCard | None
    valid_until: datetime | None
    # Метка каталога, по которому собрана запись; пустая — запись не кешировалась.
    catalogue: str

    def fresh(self, now: datetime, catalogue: str | None) -> bool:
        """Whether the entry still describes the person at `now` under that catalogue."""
        in_time = self.valid_until is None or now < self.valid_until
        return in_time and catalogue is not None and self.catalogue == catalogue
