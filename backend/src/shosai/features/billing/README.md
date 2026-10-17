# billing

What a person or a company has paid for and what they may use: the plan catalogue, the `Entitlements` every slice reads, the usage meters, payments through TBank, CloudPayments and lava.top, auto-renewal, workspace seats and trials, company invoices and refunds.

- Plan: [docs/plan/slices/billing.md](../../../../../docs/plan/slices/billing.md). Decisions: [ADR 0054](../../../../../docs/adr/0054-billing-plans-payments-trials-and-refunds.md).
- Public surface: `contracts` (`Entitlements`, `MinutesAllowance`, the snapshot and its types) and `contracts.events` (`billing.payment.succeeded`, `.payment.refunded`, `.subscription.changed`, `.seats.changed`, `.quota.exhausted`).

## Rules the domain holds

- `domain/money.py`, `currency.py` — minor units in RUB, USD and EUR, never converted or mixed; a period's prices all zero or all positive; the currency by country, never the client's.
- `domain/plans.py` — the cabinet's plan: slug, audience, seats, monthly and yearly prices, limits (`None` unlimited, `0` not included), capabilities, weekly tokens per model tier.
- `domain/entitlements.py` — entitlements by time alone: the plan holds until its expiry, then 7 days of grace only while auto-renewal is on; a trial ends without grace; past that, the Free plan.
- `domain/meters.py` — the UTC month of minutes and the Monday week of tokens; minutes judged on raw seconds; a frontier request spends packs then falls back to a standard model, a standard one past its daily tokens stops.
- `domain/promos.py`, `periods.py` — promo status and discounts; the renewal key `<subscription>:<date>`; prorated seats and refunds of the unused part, rounded down.
