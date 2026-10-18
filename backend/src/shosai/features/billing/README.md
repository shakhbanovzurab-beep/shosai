# billing

What a person or a company has paid for and what they may use: the plan catalogue, the `Entitlements` every slice reads, the usage meters, payments through TBank, CloudPayments and lava.top, auto-renewal, workspace seats and trials, company invoices and refunds.

- Plan: [docs/plan/slices/billing.md](../../../../../docs/plan/slices/billing.md). Decisions: [ADR 0054](../../../../../docs/adr/0054-billing-plans-payments-trials-and-refunds.md).
- Public surface: `contracts` (`Entitlements`, `MinutesAllowance`, `UsageTombstones`, `TokenAllowanceReader`, the `MeetingMinutes` port meetings binds, the snapshot, its types and errors) and `contracts.events` (`billing.payment.succeeded`, `.payment.refunded`, `.subscription.changed`, `.seats.changed`, `.quota.exhausted`).

## Rules the domain holds

- `domain/money.py`, `currency.py` — minor units in RUB, USD and EUR, never converted or mixed; a period's prices all zero or all positive; the currency by country, never the client's.
- `domain/plans.py` — the cabinet's plan: slug, audience, seats, monthly and yearly prices, limits (`None` unlimited, `0` not included), capabilities, weekly tokens per model tier; each broken rule carries its API code (`plan_*`).
- `domain/entitlements.py` — entitlements by time alone: the plan holds until its expiry, then 7 days of grace only while auto-renewal is on; a trial ends without grace; queued plans run one after another from the expiry, without grace; past that, the Free plan; `next_change` is the next moment the plan in force may change.
- `domain/meters.py` — the UTC month of minutes and the Monday week of tokens; minutes judged on raw seconds; a frontier request spends packs then falls back to a standard model, a standard one past its daily tokens stops.
- `domain/promos.py`, `periods.py` — promo rules with their codes (`promo_*`), the status in the cabinet's order (disabled, expired, exhausted, scheduled, active) and discounts; the renewal key `<subscription>:<date>`; prorated seats and refunds of the unused part, rounded down.

## Catalogue (EU home only)

- Tables `tariffs`, `promo_codes`, `payment_routes` exist only in the EU home (revision `f1b7c3e9a05d`); the migration seeds the Free plan (`FREE_PLAN_ID`) and the draft's payment routes.
- Admin routes in the cabinet's contract: `/v1/admin/plans*` and `/v1/admin/promo-codes*` behind identity's admin session. A plan with subscribers is archived instead of deleted, an archived plan is off sale and edited only while restored; a deleted plan leaves every promo code, and a code left with no plan is switched off. The Free plan is never removed, archived, priced or renamed off its slug (`free_plan_locked`).
- A plan's subscribers are counted in both homes through `billing_plan_holders` (counts only, past row-level security): subscribers now for the list, every subscription naming the plan for the archive-or-delete decision.

## Subscriptions and entitlements

- `subscriptions` (one row per person; `expires_at` is the authority; `version` rises with every change) and `subscription_segments` (plans queued behind it), in each home, personal by row-level security; revision `a4c2e8f61b93`.
- `SubscriptionLedger.record` is the one way to change what a person holds: it writes the row with its version, replaces the queue, adds `billing.subscription.changed` and raises the cache's version floor before the commit.
- `Entitlements` (`EntitlementSnapshots`): the entry is cached in Valkey per person until the plan in force changes by time, at most 10 minutes; it is stored only when its version reaches the floor and its catalogue mark is current (one Lua script), so a reader that saw the database before a change never stores it; every committed catalogue edit changes the mark. On a miss the subscription (person's home) and the catalogue (EU) are read at once; an outage of either with no cached entry is `EntitlementsUnavailableError` (503).
- Billing's part of the native `/v1/auth/me`: `subscription` (the draft's card of the bought plan, none without a subscription), `quota` (the month's minutes), `features` (teleprompter with a paid plan; voice switches stay the draft's defaults until the agent slice).

## Minutes (BL-D3)

- `usage_events` (revision `b7e1d4a90c26`): a tombstone per deleted meeting in the UTC month the meeting started, written once in the deleting transaction through `UsageTombstones`; monthly partitions keep the current and the previous month (ADR 0007 as amended), and a meeting older than that leaves none.
- `MinutesMeter` counts the month live, never cached: meetings that still exist (`MEETING_MINUTES`, bound by meetings; none until then) plus tombstones. `check` refuses at the limit (402 `minutes_exhausted`), `covers` refuses an upload longer than the minutes left before processing (402 `upload_exceeds_minutes`).
- `free_plan_devices`: a Free account claims its desktop device by the SHA-256 of its id or machine name on its first check; another Free account on it is refused (403 `free_plan_device_taken`); paid accounts neither claim nor are refused. Claims are per home (inv-2 allows no device hash outside it).

## Tokens and packs (BL-D4)

- Billing counts tokens itself (owner's decision, 2026-10-17): F6's guard keeps its money ceilings, the plan's token limits never reach `CallContext.spend_limits`.
- `TokenSettlement`, billing's `CostSettlement`, runs once per cost row in its transaction: an interactive expensive call counts for the frontier tier, a standard one for the standard tier (essential calls and Leo's background work are not counted); tokens go to the Monday week and, for standard, the UTC day in `token_usage` (one row per person, tier and period; a row of an older period changes nothing); tokens past the frontier week's allowance are debited from `premium_credit_ledger`, keyed by the cost id.
- `TokenStanding` (`billing.token_allowance`) answers before a request, live: within the allowance, from packs, fall back to a standard model (`frontier_weekly_tokens`) or stop (`standard_daily_tokens`, `standard_weekly_tokens`). Concurrent requests may pass the allowance by what is in flight; packs are never spent twice (the week's row lock).
