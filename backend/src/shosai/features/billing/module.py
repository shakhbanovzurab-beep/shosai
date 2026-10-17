"""The billing slice as composition sees it (billing plan §3.1).

Step 2 adds the catalogue in the EU home and the admin's plan and promo code routes;
subscriptions, the entitlements, the meters and the payments join in the later steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.billing.application.catalogue import Catalogue
from shosai.features.billing.application.promo_codes import PromoCodes
from shosai.features.billing.channels.http.admin_plans import build_admin_plans_router
from shosai.features.billing.channels.http.admin_promo_codes import (
    build_admin_promo_codes_router,
)
from shosai.features.billing.contracts.events import (
    PaymentRefunded,
    PaymentSucceeded,
    QuotaExhausted,
    SeatsChanged,
    SubscriptionChanged,
)
from shosai.features.billing.infrastructure.plan_records import TariffRecord
from shosai.features.billing.infrastructure.promo_records import (
    PaymentRouteRecord,
    PromoCodeRecord,
)
from shosai.features.billing.infrastructure.subscriber_counts import NoSubscriptions


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The admin's catalogue routes over the EU home."""
    catalogue = Catalogue(services.transactions, NoSubscriptions())
    codes = PromoCodes(services.transactions)
    yield FeatureParts(
        http_routers=(
            build_admin_plans_router(catalogue, services.ports),
            build_admin_promo_codes_router(codes, services.ports),
        ),
    )


BILLING = FeatureModule(
    name="billing",
    build=build,
    models=(TariffRecord, PromoCodeRecord, PaymentRouteRecord),
    events=(PaymentSucceeded, PaymentRefunded, SubscriptionChanged, SeatsChanged, QuotaExhausted),
)
