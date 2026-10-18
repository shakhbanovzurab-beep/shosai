"""Billing's payment metrics: the inv-4 counter reconciliation feeds (§16.4).

`shosai_billing_unrecorded_payments_total` counts acquirer payments found acknowledged
without a committed transaction row; it is exported from the start at zero, so the
monitor can tell a healthy zero from a missing series.
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter

UNRECORDED_PAYMENTS: Final = "shosai_billing_unrecorded_payments_total"


class PaymentMetrics:
    """The process's payment counters."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._unrecorded = Counter(
            UNRECORDED_PAYMENTS.removesuffix("_total"),
            "Платежи, подтверждённые эквайеру без зафиксированной строки транзакции",
            registry=registry,
        )

    def unrecorded_payment(self) -> None:
        """Count one acknowledged payment reconciliation found without its row."""
        self._unrecorded.inc()
