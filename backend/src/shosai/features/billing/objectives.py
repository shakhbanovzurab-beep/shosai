"""Billing's invariant monitors (§16.4): no payment acknowledged without its committed row.

The counter is billing's own: reconciliation (step 8) counts every acquirer payment it
finds acknowledged with no committed transaction row; any increase pages (inv-4).
"""

from shosai.core.observability.objectives import InvariantMonitor, NeverIncreases
from shosai.features.billing.infrastructure.payment_metrics import UNRECORDED_PAYMENTS

BILLING_MONITORS = (
    InvariantMonitor(
        name="unrecorded_payment",
        invariant="inv-4",
        summary="Эквайер подтвердил платёж, которого нет в базе",
        explanation=(
            "Сверка нашла оплату, о которой эквайер получил подтверждение, но строки "
            "транзакции нет: человек заплатил и может не получить оплаченное, а деньги не "
            "учтены. Платёж нужно найти по номеру заказа у эквайера и провести вручную."
        ),
        condition=NeverIncreases(UNRECORDED_PAYMENTS),
    ),
)
