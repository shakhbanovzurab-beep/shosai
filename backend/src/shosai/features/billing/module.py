"""The billing slice as composition sees it (billing plan §3.1).

Step 2 added the catalogue in the EU home with the admin's plan and promo code routes;
step 3 subscriptions, the cached `Entitlements` and billing's part of the native
`/v1/auth/me`. Step 4 adds the month's minutes with their allowance, and step 5 the weekly
tokens, the packs ledger and its settlement of cost rows. Payments join in later steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.billing.application.account_data import ACCOUNT_DATA, BillingAccountData
from shosai.features.billing.application.catalogue import Catalogue
from shosai.features.billing.application.entitlement_snapshots import EntitlementSnapshots
from shosai.features.billing.application.minutes import MinutesMeter
from shosai.features.billing.application.native_me import BillingMe
from shosai.features.billing.application.promo_codes import PromoCodes
from shosai.features.billing.application.tokens import TokenSettlement, TokenStanding
from shosai.features.billing.channels.http.admin_plans import build_admin_plans_router
from shosai.features.billing.channels.http.admin_promo_codes import (
    build_admin_promo_codes_router,
)
from shosai.features.billing.contracts import (
    ENTITLEMENTS,
    MINUTES_ALLOWANCE,
    TOKEN_ALLOWANCE,
    USAGE_TOMBSTONES,
)
from shosai.features.billing.contracts.events import (
    PaymentRefunded,
    PaymentSucceeded,
    QuotaExhausted,
    SeatsChanged,
    SubscriptionChanged,
)
from shosai.features.billing.infrastructure.entitlement_cache import EntitlementCache
from shosai.features.billing.infrastructure.minutes_records import (
    FreePlanDeviceRecord,
    UsageEventRecord,
)
from shosai.features.billing.infrastructure.plan_holders import SubscriptionHolders
from shosai.features.billing.infrastructure.plan_records import TariffRecord
from shosai.features.billing.infrastructure.promo_records import (
    PaymentRouteRecord,
    PromoCodeRecord,
)
from shosai.features.billing.infrastructure.subscription_records import (
    SubscriptionRecord,
    SubscriptionSegmentRecord,
)
from shosai.features.billing.infrastructure.token_records import (
    CreditLedgerRecord,
    TokenUsageRecord,
)
from shosai.features.identity.contracts import ME_CONTRIBUTIONS


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The admin's catalogue routes and the entitlement ports."""
    cache = EntitlementCache(services.valkey)
    snapshots = EntitlementSnapshots(services.transactions, cache)
    meter = MinutesMeter(services.transactions, (snapshots, services.ports))
    catalogue = Catalogue(
        services.transactions, (SubscriptionHolders(services.transactions), cache)
    )
    yield FeatureParts(
        http_routers=(
            build_admin_plans_router(catalogue, services.ports),
            build_admin_promo_codes_router(PromoCodes(services.transactions), services.ports),
        ),
        provides=(
            ENTITLEMENTS.bind(snapshots),
            ME_CONTRIBUTIONS.bind(BillingMe(snapshots, meter)),
            MINUTES_ALLOWANCE.bind(meter),
            USAGE_TOMBSTONES.bind(meter),
            TOKEN_ALLOWANCE.bind(TokenStanding(services.transactions, snapshots)),
            ACCOUNT_DATA_HANDLERS.bind(BillingAccountData(services.transactions)),
        ),
        cost_settlements=(TokenSettlement(snapshots),),
    )


BILLING = FeatureModule(
    name="billing",
    build=build,
    account_data=(ACCOUNT_DATA,),
    models=(
        TariffRecord,
        PromoCodeRecord,
        PaymentRouteRecord,
        SubscriptionRecord,
        SubscriptionSegmentRecord,
        UsageEventRecord,
        FreePlanDeviceRecord,
        TokenUsageRecord,
        CreditLedgerRecord,
    ),
    events=(PaymentSucceeded, PaymentRefunded, SubscriptionChanged, SeatsChanged, QuotaExhausted),
)
