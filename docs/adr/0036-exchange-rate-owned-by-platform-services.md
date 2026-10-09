# ADR 0036 — The USD/RUB rate is owned by platform services, not by billing

- **Status:** accepted by the owner on 2026-10-08 (F6 planning, decision F6-D4).
- **Packages:** F6 (`core/exchange_rates`); S03 reads the rate for prices and acquirers.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §6 (platform tables: exchange rates); [ADR 0005](0005-data-without-owner-in-eu-home.md); [DATA_MAPPING.md](../plan/DATA_MAPPING.md) `exchange_rates`; [FEATURE_MAP.md](../plan/FEATURE_MAP.md) §2.5; [F6 plan](../plan/packages/F6-platform-services.md).

## Context

A cost row of the draft snapshots the ruble amount at the Central Bank rate of the moment (`cost_rub`, `exchange_rate_used`), and the admin cost reports sum `cost_usd × exchange_rate_used`. The rate is fetched every 6 hours from `cbr-xml-daily.ru` by `billing.refresh_rates` into the platform table `exchange_rates` (draft `tasks/refresh_rates.py`, `config.py:798`); D4 gave that task to S03. S03 comes after F6, while F6 writes cost rows from its first step.

## Decision

1. `core/exchange_rates` owns the platform table `exchange_rates` (EU home, append-only, as DATA_MAPPING maps it), the periodic job that fetches the Central Bank rate every 6 hours, and a read port `ExchangeRates` with the latest USD/RUB rate, cached 60 s in each process.
2. A cost row stores `cost_usd`, `exchange_rate_used` and `cost_rub` at the rate the port returns. When no rate exists yet (an empty table before the first fetch), the two ruble columns stay empty and the row is counted; a rate older than 3 days raises a ticket alert. A cost row is never refused for want of a rate.
3. S03 reads the rate through the same port. Its own rules — the 1.30 markup, rounding down, the fallback for prices shown to users — stay in S03.
4. FEATURE_MAP §2.5 moves `billing.refresh_rates` from S03 to F6.

## Consequences

- Cost rows carry rubles from F6's first step; admin reports keep the draft's arithmetic.
- The rate fetch is one more outbound HTTP call of the scheduler's periodic jobs, with a 10 s deadline and the next interval as its retry.

## Revisit when

- Billing needs a rate from another source (an acquirer's rate, a bank's rate) for money it charges → that rate becomes S03's own, beside this one.
