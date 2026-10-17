"""The billing slice as composition sees it (billing plan §3.1).

Step 1 publishes the contract and the events; tables, the entitlements, the meters and
the payments join in the later steps of the plan.
"""

from shosai.core.features import FeatureModule
from shosai.features.billing.contracts.events import (
    PaymentRefunded,
    PaymentSucceeded,
    QuotaExhausted,
    SeatsChanged,
    SubscriptionChanged,
)

BILLING = FeatureModule(
    name="billing",
    events=(PaymentSucceeded, PaymentRefunded, SubscriptionChanged, SeatsChanged, QuotaExhausted),
)
