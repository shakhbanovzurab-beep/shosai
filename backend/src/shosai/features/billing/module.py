"""The billing slice as composition sees it (billing plan §3.1).

Step 2 added the catalogue in the EU home with the admin's plan and promo code routes;
step 3 subscriptions, the cached `Entitlements` and billing's part of the native
`/v1/auth/me`. Step 4 adds the month's minutes with their allowance, and step 5 the weekly
tokens, the packs ledger and its settlement of cost rows, and step 6 the person's plans,
usage and sales inquiries; step 7 Leo's plan and usage tools and the inv-4 monitor.
Payments join in later steps.
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
from shosai.features.billing.application.people_views import PeopleViews
from shosai.features.billing.application.promo_codes import PromoCodes
from shosai.features.billing.application.sales import SalesInquiries
from shosai.features.billing.application.tokens import TokenSettlement, TokenStanding
from shosai.features.billing.channels.agent_tools import BILLING_TOOLS, billing_tools
from shosai.features.billing.channels.http.admin_plans import build_admin_plans_router
from shosai.features.billing.channels.http.admin_promo_codes import (
    build_admin_promo_codes_router,
)
from shosai.features.billing.channels.http.plans import build_plans_router
from shosai.features.billing.channels.http.usage import build_usage_router
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
    SalesInquiryReceived,
    SeatsChanged,
    SubscriptionChanged,
)
from shosai.features.billing.infrastructure.entitlement_cache import EntitlementCache
from shosai.features.billing.infrastructure.minutes_records import (
    FreePlanDeviceRecord,
    UsageEventRecord,
)
from shosai.features.billing.infrastructure.payment_metrics import PaymentMetrics
from shosai.features.billing.infrastructure.plan_holders import SubscriptionHolders
from shosai.features.billing.infrastructure.plan_records import TariffRecord
from shosai.features.billing.infrastructure.promo_records import (
    PaymentRouteRecord,
    PromoCodeRecord,
)
from shosai.features.billing.infrastructure.sales_records import SalesInquiryRecord
from shosai.features.billing.infrastructure.subscription_records import (
    SubscriptionRecord,
    SubscriptionSegmentRecord,
)
from shosai.features.billing.infrastructure.token_records import (
    CreditLedgerRecord,
    TokenUsageRecord,
)
from shosai.features.billing.objectives import BILLING_MONITORS
from shosai.features.identity.contracts import ME_CONTRIBUTIONS


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The admin's catalogue routes and the entitlement ports."""
    business = services.settings.calendar.business
    cache = EntitlementCache(services.valkey)
    snapshots = EntitlementSnapshots(services.transactions, cache)
    meter = MinutesMeter(services.transactions, (snapshots, services.ports), business=business)
    views = PeopleViews(
        services.transactions, (snapshots, meter, services.ports), business=business
    )
    inquiries = SalesInquiries(services.transactions, services.outbox)
    standing = TokenStanding(services.transactions, snapshots, business=business)
    # Счётчик inv-4 виден с нуля во всех ролях; растить его будет сверка платежей (шаг 8).
    PaymentMetrics(services.registry)
    catalogue = Catalogue(
        services.transactions, (SubscriptionHolders(services.transactions), cache)
    )
    yield FeatureParts(
        http_routers=(
            build_admin_plans_router(catalogue, services.ports),
            build_admin_promo_codes_router(
                PromoCodes(services.transactions, business=business), services.ports
            ),
            build_plans_router(views, inquiries, services.ports, services.rate_limiter),
            build_usage_router(views, services.ports),
        ),
        provides=(
            ENTITLEMENTS.bind(snapshots),
            ME_CONTRIBUTIONS.bind(BillingMe(snapshots, meter, business=business)),
            MINUTES_ALLOWANCE.bind(meter),
            USAGE_TOMBSTONES.bind(meter),
            TOKEN_ALLOWANCE.bind(standing),
            ACCOUNT_DATA_HANDLERS.bind(BillingAccountData(services.transactions)),
        ),
        cost_settlements=(TokenSettlement(snapshots, business),),
        agent_tools=billing_tools(views, standing),
    )


BILLING = FeatureModule(
    name="billing",
    build=build,
    account_data=(ACCOUNT_DATA,),
    monitors=BILLING_MONITORS,
    agent_tools=BILLING_TOOLS,
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
        SalesInquiryRecord,
    ),
    events=(
        PaymentSucceeded,
        PaymentRefunded,
        SubscriptionChanged,
        SeatsChanged,
        QuotaExhausted,
        SalesInquiryReceived,
    ),
)
