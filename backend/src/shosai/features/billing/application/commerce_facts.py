"""The catalogue's plans and promo codes for the platform operator's Leo (agent plan AG-D5).

What the admin's plans and promo codes screens already read, as plain facts: a plan's
audience, prices per currency in minor units and its subscribers; a code's discount, use and
status on today's business date.
"""

from collections.abc import Sequence

from shosai.features.billing.application.catalogue import Catalogue
from shosai.features.billing.application.promo_codes import PromoCodes
from shosai.features.billing.contracts import PlanSummary, PromoSummary
from shosai.features.billing.domain.money import Prices
from shosai.features.billing.domain.plans import BillingPeriod


def minor_units(prices: Prices | None) -> dict[str, int]:
    """A period's prices by currency, in minor units; none for a period the plan lacks."""
    return (
        {}
        if prices is None
        else {currency.value: amount for currency, amount in prices.amounts.items()}
    )


class CommerceFactsReader:
    """Reads the catalogue for the operator."""

    def __init__(self, catalogue: Catalogue, codes: PromoCodes) -> None:
        self._catalogue = catalogue
        self._codes = codes

    async def plans(self) -> Sequence[PlanSummary]:
        """Every plan, archived ones included, in the pricing page's order."""
        return [
            PlanSummary(
                slug=item.plan.slug, name=item.plan.name, audience=item.plan.audience.value,
                subscribers=item.subscribers, on_sale=item.plan.on_sale,
                archived=item.plan.archived,
                month_prices=minor_units(item.plan.prices.get(BillingPeriod.MONTH)),
                year_prices=minor_units(item.plan.prices.get(BillingPeriod.YEAR)),
            )
            for item in await self._catalogue.plans()
        ]  # fmt: skip

    async def promo_codes(self) -> Sequence[PromoSummary]:
        """Every promo code with its status on today's business date."""
        today = self._codes.today()
        return [
            PromoSummary(
                code=item.promo.code, status=item.promo.status(today).value,
                percent_off=item.promo.percent_off, redemptions=item.promo.redemptions,
                max_redemptions=item.promo.max_redemptions, valid_until=item.promo.valid_until,
            )
            for item in await self._codes.codes()
        ]  # fmt: skip
