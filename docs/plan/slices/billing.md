# billing — slice plan

Prompt: [prompts/S-feature-slice.md](../prompts/S-feature-slice.md), launched through [BACKEND-next-step.md](../prompts/BACKEND-next-step.md). Status: [STATUS.md](../STATUS.md). Slice card: [SLICE_MAP.md §4.2.3](../SLICE_MAP.md#3-billing).

`billing` owns what a person or a company has paid for and what they may use: the plan catalogue, the `Entitlements` every slice reads, the usage meters, payments through three acquirers, auto-renewal, workspace seats and company invoices. Its first step group, **billing·entitlements**, comes in wave 1 so that files, meetings, capture and Leo are written against real plans and limits; payments, seats and invoices come in wave 3 and unblock workspaces' screens.

- **Status:** written on 2026-10-17 and approved by the owner the same day: BL-D1, BL-D2, BL-D6, BL-D7 as proposed, BL-D3, BL-D4, BL-D5, BL-D8 with the owner's amendments (§2), recorded in [ADR 0054](../../adr/0054-billing-plans-payments-trials-and-refunds.md); ADR 0007 amended.
- **Philosophy check:** a person sees one plan, one usage view and one way to pay; nothing to re-enter at renewal; money never moves twice or silently. Limits are said plainly where they bite (a meeting meter, a locked feature with the plan that opens it), never as a stream of upsell notices. The receipt and the renewal notice are the only emails the slice sends on its own.

---

## 1. Facts this plan rests on

### 1.1 Inputs

| Source | Fact |
|---|---|
| [SLICE_MAP](../SLICE_MAP.md) §4.2.3, §2.1, §2.9, §2.10, §2.11, §3, §5, §8.1 | Scope: catalogue with prices per currency, limits and capabilities; promo codes; the `Entitlements` port (fail closed, inv-3); minutes per month with ADR 0007 tombstones, model tokens per week by tier from F6 cost rows, token packs; hosted checkout and portal for three acquirers; auto-renewal and reconciliation; workspace seats monthly or yearly; company invoices with bank-statement matching (fr-15); refunds; sales inquiries; admin plans, promo and billing; referral and affiliate history (SM-9: frozen at cutover, balances paid by hand). Owns `subscriptions`, `subscription_segments`, `transactions`, `auto_charge_attempts`, `auto_renew_consents`, `card_bindings`, `recurring_payment_methods`, `premium_credit_ledger`, `usage_events`, `referral_rewards`, `affiliate_*`, `org_invoices`; EU platform `tariffs`, `promo_codes`, `payment_routes`. External webhooks `POST /v1/billing/webhook/{provider}` and `…/{provider}/{kind}` (tbank, cloudpayments, lava, lava_paypal, legacy moneta). One catalogue (others reference it by id) and one usage view (§2.11). billing·entitlements = catalogue, free plan, `Entitlements`, minutes meter (wave 1); payments, seats, invoices (wave 3) |
| Target architecture | fr-5, fr-15; nfr-10 (zero double charges, acknowledge after commit), nfr-18. §4.2: acquirers TBank, CloudPayments, lava.top; bank statement API. §8.1 Payment: `transactions`, `auto_charge_attempts`, outbox in the same transaction, period key `subscription:date`, transaction and subscription row locks, unknown outcome stays `charging` until reconciliation, never deleted; Company invoice: `org_invoices`, PDF in the bucket, number from a home sequence, matched once, payment + seats + audit in one transaction. §9 inv-3, inv-4, inv-5, inv-13, inv-16. §10: webhook answers within 5 s after commit, reconciliation every minute; `POST /v1/billing/workspaces/{id}/invoices`. §11 flows 6 and 7. §13.2: bank API down → seats active until the paid period + 7 days. §14 rule 3: acknowledge after commit, period changes through one function under the subscription row lock (`FOR UPDATE` with `populate_existing`), side effects through the outbox. §15: webhook signatures checked before parsing. §22: tax and closing documents, the bank, the seat price are the owner's |
| [DATA_MAPPING](../DATA_MAPPING.md) §5.2, R1, R5, R6, R8, R12–R14, M-1…M-8, E-1…E-5 | 16 tables, 15 moved verbatim (ids, `external_id`, `renewal_period_key`, Fernet `rebill_id_ciphertext`), `usage_events` partitioned; catalogue tables in the EU home, retire-only, no FK (ADR 0005); money rows never deleted (402-FZ); `org_invoices` starts empty; M1 checks money sums and ids, credit balances, open holds, decryptable cards, and E-4 "v2's entitlement function gives the draft's result at T0" for every migrated account |
| F6 and core | `CostSettlement` hook (`core/ai/costs/settlement.py`, registered in `FeatureParts.cost_settlements`) runs in the cost row's transaction on first insert — billing debits packs there (F6-C3). Per-user ceilings come from the caller's `CallContext.spend_limits` (`SpendPeriod`: hour, day, month, expensive month, background day — **no week**). Call class `essential` is never refused by money (inv-13). Exchange rates: `CoreServices.exchange_rates` (ADR 0036); markup and rounding stay in billing. `EmailPort.enqueue` in the caller's transaction, kind `account` never suppressed |
| identity and workspaces contracts | identity: `MeContribution` (billing fills `subscription`, `quota`, `features` of the native `GET /v1/auth/me`), `AccountRegistered`, `AccountDeletionScheduled` (pause renewals), `AccountDeletionCancelled`, the account-data registry. workspaces: `SeatAllowance` (`seats`, `start_trial`; also read by the daily inv-16 sweep), `SuspensionSource.BILLING`, events `workspace.*`, `member.*` |
| Native clients ([contracts/](../../../contracts/README.md)) | `UserMeResponse.subscription` (`SubscriptionCardDTO`: status `active`/`expired`/`canceled`, `tariff` as the draft's `TariffDTO` with `price_rub`, `period_days`, `minutes_limit`, four `allow_*`), `quota` (`unlimited`, `limit_minutes`, `bonus_minutes`, `used_minutes`, `remaining_minutes`, `exhausted`), `features` (`voice_translation`, `voice`, `teleprompter`, `premium_weekly_remaining_pct`, `premium_credit_*`). Windows and macOS branch on them; meeting audio routes answer 402 `minutes_exhausted` and 403 `subscription_required`; the chat stream 402 `quota_exhausted` |
| Cabinet ([frontend/](../../../frontend)) | `/app/upgrade` (`docs/upgrade-api.md`): `GET /billing/plans` → plans by audience (individual, team, enterprise), `current_plan_id`, `seat`, `effective_plan_id`, `usage {used_minutes, limit_minutes, resets_at}` (monthly); `POST /billing/checkout {plan_id, seats?}` → `{url}`; `POST /billing/sales-inquiry`. Feature gates on `file_manager_gb`, `knowledge_base_mb`; the meetings meter stops recording until `resets_at`. Settings › Billing (`docs/settings-api.md`): plan, renewal, payment methods, invoices, `POST /settings/billing/portal {intent}` → `{url}`; Settings › Usage: weekly tokens per tier (`standard`, `frontier`), frontier spend per model, packs, `POST /settings/usage/top-up {pack_id}` → `{url}`. Workspace plan section and seat meter. Admin › Plans and promo codes (plan with `slug`, `audience`, `seats`, `custom_pricing`, `price_monthly`/`price_yearly` in RUB, USD, EUR minor units, `limits`, `capabilities`, `features`, archive instead of delete; promo with `percent`/`fixed`, scope, period, limits, dates, first payment only) and Admin › Billing (overview per currency, transactions with refunds and invoices). **Every flow is a redirect to `{url}`; the docs name Stripe, which Shosai does not use** |

### 1.2 The draft, for lessons

Read in `/root/whisperer/backend/src/meetassist/` (`features/billing/*`, `services/{billing_service,tariff_service,subscription_stack,auto_renew_*,card_binding_service,promo_service,pricing}.py`, `services/payment/*`, `api/{me_billing,billing_webhook}.py`, `api/admin/{finance,tariffs,promocodes,payments}.py`), `docs/AUDIT.md`, specs 009, 012, 019, 024, 025, 028, 030, 051, 059, 060, 065, 070.

| Draft fact or incident | Rule in v2 |
|---|---|
| The webhook's commit ran after the response (a `get_db` dependency of request scope), so an acquirer could be acknowledged for a row that never committed | The webhook commits its transaction explicitly, then answers; a test kills the transaction before commit and sees a 5xx |
| 24.09.2026: webhook and polling both granted one purchase (7 days became 14): a stale `pending` row was read before the lock | One `confirm` function: `SET LOCAL lock_timeout '5s'`, `SELECT … FOR UPDATE` with `populate_existing`, a terminal status changes nothing; concurrency test with 20 confirmations |
| 20.09.2026: lava cannot cancel invoices, so a second invoice was issued minutes after the first was paid; lava never delivered a webhook (56 provider subscriptions, 0 rows) | Checkout reuses a pending order of the same user, product, amount, provider within 30 minutes and first reconciles older pending orders; reconciliation polls every provider, lava's subscriptions through their feed |
| TBank `AUTHORIZED` counted as paid at checkout, but as frozen money elsewhere | Only `CONFIRMED` (TBank), `Completed` (CloudPayments), `payment.success` (lava) grant anything |
| An expired paid plan kept unlimited minutes (nothing marked it expired; the quota read the plan whatever its state) | Entitlements are computed from time, never from a stored status: a lapsed plan gives the Free plan's limits |
| A refund kept the paid days | A refund ends the days it paid for (and reverses credits, rewards, commissions) |
| A grant on a zero-cost payment paid a 500 ₽ referral reward (AFF-02); missing row locks and no unique `external_id` duplicated bonuses (BILL-02) | Every grant follows from exactly one successful transaction with a non-zero amount (inv-5); `external_id` unique; promo uses counted by one conditional update |
| Auto-renew: explicit consent (376-FZ) with the disclosed amount, period and terms; three-phase charge (record `charging` → call outside any transaction → record the outcome); unknown outcome reconciled, never retried blindly; a price change stops auto-renew with an email | Kept as written; the capability check that decides consent also decides recurrence (the draft's bug of checking by provider name) |
| Payment routing is data (`payment_routes`), offered only where credentials exist; prices set per currency by the admin, never converted; currency chosen by the server from the country | Kept; the currency follows the account's country and home, never the client |
| Credits were Max-only USD, spent after a $4.50 weekly budget, with a quiet fallback to a standard model; the ledger clamps reversals | Replaced by the cabinet's tokens per tier and packs (BL-D4); the ledger discipline and the quiet fallback are kept |
| Fiscal receipts (54-FZ) through TBank and CloudKassir; lava none | Kept per provider |

---

## 2. Decisions

Decided by the owner on 2026-10-17 (ADR 0054). The table keeps the question and the decision as taken; the owner's amendments are in the decision.

| ID | Question | Decision | Step |
|---|---|---|---|
| **BL-D1** | The cabinet's contract names Stripe; the architecture, the draft and the shipped flows use TBank, CloudPayments and lava.top | **TBank and CloudPayments for roubles, lava.top with PayPal for other currencies, behind one provider port chosen by `payment_routes`.** The cabinet keeps its redirect contract (`{url}`); adding a card is the acquirer's card-binding page; turning auto-renewal off is a switch in Settings › Billing. Stripe is removed from the cabinet's documents (done with the plan) | 9 |
| **BL-D2** | The cabinet's plan model or the draft's tariffs | **The cabinet's model** (table `tariffs` keeps its name for M1); the draft's plans migrate as archived plans with their limits, so a migrated subscription keeps exactly what it bought (E-4); the native `TariffDTO` is derived from the plan | 2 |
| **BL-D3** | The Free plan's minutes | **120 minutes a month; a deleted meeting's minutes stay counted in its month** (ADR 0007 amended). **Against abuse:** an uploaded recording is checked against the minutes left before processing — a file longer than them is not processed and the person is offered a plan; at most one Free account per desktop device; registration refuses disposable mail domains (identity, its step 15) | 4 |
| **BL-D4** | Tokens per tier, packs, the missing weekly ceiling | **Weekly token allowances per tier; packs never expire and are spent after the weekly allowance; F6 gains `WEEK`.** When the allowance and the packs are gone, Leo answers with a standard model without an error and adds a short note under the answer — the standard model answered because the limit is used up — with a link to the packs. The standard model has a daily limit per plan through F6's ceilings; when it is used up the person gets a clear message, not unlimited use | 5 |
| **BL-D5** | A workspace's trial | **14 days without a card; one trial per person for the account's lifetime and one per work mail domain; a person belongs to at most one trial workspace at a time; at most 5 seats and the limits of the ordinary paid plan.** Reminders to the owner in the cabinet 3 days and 1 day before the end. **At the trial's end the workspace is suspended at once, with no grace;** the 7 days of grace apply only to a failed renewal of a paid subscription. **A suspended unpaid workspace is deleted after 90 days, with warnings to the owner 30, 7 and 1 day before;** paying before then restores everything as it was | 12 |
| **BL-D6** | Company invoices without a bank | **Invoices with their PDF at once; the platform's admin marks one paid; the bank-statement matcher comes with the bank** | 13 |
| **BL-D7** | Seats changed mid-period | **Added seats are paid at once for the rest of the period (by card or a supplementary invoice); removed seats take effect at the next renewal** | 12 |
| **BL-D8** | Refunds | **Through TBank's and CloudPayments' APIs, lava by hand in its dashboard (matched by its event). Only the unused part is returned — used packs and minutes are not; a refund ends the days it paid for** | 14 |

Settled by documents, no decision needed: commit before acknowledging (nfr-10); one charge per order and per period (inv-4); one grant per transaction (inv-5); fail-closed entitlements (inv-3); prices per currency, never converted; currency by country; referral and affiliate frozen (SM-9); events with three-part names.

---

## 3. Design

### 3.1 Layout

```
backend/src/shosai/features/billing/
  contracts/            # Entitlements, MinutesAllowance, events (events.py)
  settings.py           # BillingSettings: grace days, credentials per acquirer, routing defaults
  module.py, objectives.py, README.md
  domain/               # plans and prices, entitlements (time-based), minutes and token meters,
                        #   promo rules, currency by country, proration, period keys
  application/          # catalogue, subscriptions, entitlement snapshots, usage, checkout,
                        #   confirm (the one function), renewals, seats, invoices, refunds
  infrastructure/       # tables and repositories; providers/ (tbank, cloudpayments, lava);
                        #   PDF invoices; the Valkey snapshot cache
  channels/http/        # plans, checkout, settings billing and usage, webhooks, admin
  channels/tasks.py     # reconciliation, renewals, expiry notices, price consistency
  channels/consumers.py # identity and workspaces events
  channels/agent_tools.py
```

### 3.2 Public surface

| Item | Kind | Used by |
|---|---|---|
| `Entitlements.snapshot(session, user_id, org_id?) -> EntitlementSnapshot` | port: plan, tier, limits, capabilities, `spend_limits` for `CallContext`, paid-until; cached in Valkey per account with a version bumped on every change, read from the database on a miss; **unavailable → `EntitlementsUnavailableError` (503), never a guess** | every slice; agent's `PrincipalFactory`; files (`file_manager_gb`), knowledge (`knowledge_base_mb`), studio (models of the plan) |
| `MinutesAllowance.check(session, user_id, device) -> MinutesLeft`, `covers(session, user_id, seconds)` | port: the live monthly count, never cached; 402 `minutes_exhausted`; an upload is pre-checked by its duration (BL-D3); a Free account is refused on a desktop device another Free account claimed (403 `free_plan_device_taken`) | meetings, capture |
| `SeatAllowance` | binds workspaces' port, extended with `trialing(session, org_ids)` so a join refuses a second trial workspace (BL-D5) | workspaces |
| `MeContribution` | binds identity's multi-port: `subscription`, `quota`, `features` in the draft's shapes | identity's native `/v1/auth/me` |
| `CostSettlement` | binds F6's hook: debits packs once per cost row | core |
| Events | `billing.payment.succeeded`, `billing.subscription.changed`, `billing.seats.changed`, `billing.quota.exhausted`, `billing.payment.refunded` (ids, amounts in minor units, codes) | workspaces (seats, suspension), alerting (ADR 0052), proactive |

### 3.3 Data (per home unless EU)

- **EU platform:** `tariffs` (slug, audience, seats range, custom pricing, prices per period and currency, limits, capabilities, features, sort, featured, archived, legacy fields for `TariffDTO`), `promo_codes`, `payment_routes`.
- **Home:** `subscriptions` (an account's or a workspace's; `expires_at` is the authority, never recomputed), `subscription_segments`, `transactions` (unique `external_id`; money in minor units per currency; never deleted), `auto_charge_attempts` (unique `(subscription_id, renewal_period_key)`), `auto_renew_consents`, `recurring_payment_methods` (Fernet), `card_bindings`, `premium_credit_ledger` (packs in tokens; never deleted), `usage_events` (monthly partitions), `org_invoices` (number from a home sequence; PDF in the home's bucket), frozen `referral_rewards` and `affiliate_*`, `billing_notices` (the draft's Valkey "expiry notified" marker as a table).
- RLS: personal tables get user isolation, workspace subscriptions and invoices company isolation; the sweep role reads what reconciliation and inv-16 need.

### 3.4 Money flows

1. **Checkout.** Reconcile older pending orders; reuse a fresh identical one; else commit a `pending` transaction; call the provider outside the transaction; store its id and URL; answer `{url}`.
2. **Confirm** (webhook, return page polling, reconciliation): the one function, under the transaction row lock, then the subscription row lock; amount and currency must match; grant, outbox event and receipt email in the same transaction; commit; then the webhook answers.
3. **Renewal:** hourly sweep, 3 h before expiry, consent and card required; three phases; unknown outcome stays `charging`, reconciled every 10 min, page after 30 min.
4. **Seats and trials:** a workspace's subscription carries seats; joins read them through `SeatAllowance`; adding seats prorates (BL-D7). A trial (BL-D5) is granted once per person and per work mail domain, at most 5 seats, the paid plan's limits; at its end the workspace is suspended at once; a paid subscription whose renewal fails keeps 7 days of grace, then is suspended; 90 days after an unpaid suspension billing schedules the workspace's deletion through workspaces' deletion saga, with warnings 30, 7 and 1 day before; a payment before then resumes it unchanged.
5. **Invoices:** issued with a PDF; paid once by the admin's mark or later the statement matcher; payment, seats and audit in one transaction.

### 3.5 Monitors and telemetry

- inv-4 monitor: payments acknowledged without a committed row, found by reconciliation (§16.4) — `shosai_billing_unrecorded_payments_total`, `NeverIncreases`.
- An attempt stuck in `charging` over 30 min pages; price drift between the catalogue and lava's offers is a ticket.
- Business alerts through `alerting`: a payment and a refund (amounts and ids only).

### 3.6 Not in billing

- Spend ceilings and their enforcement (F6); the kill switch (F6).
- Ban (identity); billing only refunds.
- Seats' members (workspaces).

---

## 4. Steps

Steps 1–7 are **billing·entitlements** (wave 1); steps 8–18 are **billing·payments** (wave 3), each waiting for the slice named. "Docker ×4" as in other plans.

| Step | Content | Skills | Done when |
|---|---|---|---|
| 1 | **Contracts and domain.** Skeleton; contracts (§3.2); domain: plans and prices (a period's prices all zero or all positive), time-based entitlements (grace with auto-renew only, lapse → Free), tiers, minutes and token meters, promo status, currency by country, proration, period keys | fastapi, python-doctor, api-design | Hypothesis tests: a lapsed plan never grants more than Free; grace only with auto-renew; a period key is unique per subscription and date; proration never charges more than the period **Done 2026-10-17:** `features/billing` with `contracts/` (`Entitlements` and its snapshot, `EntitlementsUnavailableError`, `MinutesAllowance`, port keys) and `contracts/events.py` (five three-part events); domain: money in minor units never mixed, prices per period all zero or all positive, currency by country; the cabinet's plan with limits (weekly tokens per tier, daily standard tokens) and capabilities; entitlements by time (7 days of grace only with auto-renewal, none for a trial, then Free); the UTC month and Monday week, minutes on raw seconds with the upload pre-check, the token route (allowance → packs → fall back; standard stops at its daily limit); promo status and discounts; the renewal key and prorated seats and refunds rounded down; 30 tests with Hypothesis |
| 2 | **Catalogue.** `tariffs`, `promo_codes`, `payment_routes` (EU) with the Free plan seeded; admin catalogue and promo routes (`/v1/admin/plans*`, `/v1/admin/promo-codes*`), archive instead of delete, promo scopes cleaned on removal | fastapi, python-doctor, api-design, data-storage, Docker ×4 | The admin's contract tests pass; a plan with subscribers is archived; the catalogue reads only in the EU home **Done 2026-10-17:** revision `f1b7c3e9a05d` (EU only) with `tariffs` (prices per currency and period, limits with weekly tokens per tier and the standard daily tokens, capabilities with `frontier_models`, archive off sale, all rules as constraints), `promo_codes` (plan ids or every plan, a code with no plan only switched off) and `payment_routes` (the draft's order); the Free plan seeded at a fixed id with 120 minutes, no storage, no frontier tokens, 1 000 000 standard tokens a week and 250 000 a day (the owner's starting values, tuned in the admin); `/v1/admin/plans*` and `/v1/admin/promo-codes*` in the cabinet's contract behind the admin session, PATCH merging key by key and checked whole, coded errors; archive instead of delete with subscribers, deletion leaves promo scopes, the Free plan locked; the promo status in the cabinet's order; subscribers through `PlanSubscribers` (zero until step 3); 18 new tests |
| 3 | **Subscriptions and entitlements.** `subscriptions`, `subscription_segments`; `Entitlements` with the Valkey snapshot and version, fail closed; `MeContribution` with the draft's shapes | fastapi, python-doctor, api-design, caching, resilience-failure, Docker ×4 | The native `/v1/auth/me` passes the D1 gate with billing's fields; a change bumps the version and the next read sees it; the database out of reach and the cache empty → 503 **Done 2026-10-17:** revision `a4c2e8f61b93` in both homes: `subscriptions` (one per person, version, expiry the authority) and `subscription_segments` (queued plans running from the expiry), personal by RLS, and `billing_plan_holders` counting holders for the catalogue (a held plan is archived, never deleted); `SubscriptionLedger` writes a change with its version, event and cache floor; `Entitlements` cached in Valkey per person until the next change by time (≤ 10 min), stored only at or above the version floor and for the current catalogue mark (one Lua script), fail closed (503) with no cache; billing's `subscription`, `quota`, `features` in the native `/auth/me`, decoded as the shipped clients do; the account data handler; 10 new tests |
| 4 | **Minutes.** `usage_events` (monthly partitions, ordinary retention per amended ADR 0007), the monthly count with meetings' port (bound later; zero until then), `MinutesAllowance` with the upload pre-check and the Free-device claim (`free_plan_devices`: a hash of the device id or, for the shipped clients, of the machine name) (BL-D3) | fastapi, python-doctor, data-storage, Docker ×4 | The month resets on its first day in UTC; a deleted meeting's tombstone counts in its month; the allowance answers 402 `minutes_exhausted` at the limit; an upload longer than the minutes left is refused before processing; a second Free account on a claimed device is refused, a paid one is not **Done 2026-10-17:** revision `b7e1d4a90c26` in both homes: `usage_events` partitioned by the meeting's UTC month, keeping the current and previous month (previous created at once), a tombstone once per meeting through `UsageTombstones`; `free_plan_devices` by SHA-256, per home (inv-2); `MinutesMeter` — the live count from meetings' `MEETING_MINUTES` (unbound until meetings) and tombstones, `check` (402 `minutes_exhausted`, the Free device claim, 403 `free_plan_device_taken`), `covers` (402 `upload_exceeds_minutes`); the native quota reads it; 4 new tests |
| 5 | **Tokens and packs.** Weekly tokens per tier from `provider_costs`; F6's `WEEK` period; `premium_credit_ledger` in tokens; `CostSettlement` debiting packs once per cost row; the fallback signal the agent turns into the note under its answer, and the standard model's daily ceiling per plan in `spend_limits` (BL-D4) | fastapi, python-doctor, data-storage, consistency-coordination, Docker ×4 | A redelivered cost row debits once; a pack is spent only after the weekly allowance; the week resets on Monday 00:00 UTC; with the allowance and packs gone the snapshot says "fall back", with the daily standard ceiling gone it says "stop" with its reason **Done 2026-10-17:** the owner chose billing's own token count over F6's money ceilings (no `WEEK`, no token limits in `spend_limits`); revision `c93f5a2e7d18` in both homes: `token_usage` (the Monday week per tier and the standard day, one row per period) and `premium_credit_ledger` (append-only, a debit unique per cost row); `SettledCost` gains `origin`, `created_at` and `tokens`; `TokenSettlement` counts interactive standard and expensive rows and debits packs past the frontier allowance; `TokenStanding` (`billing.token_allowance`) gives within / from packs / fall back / stop with its limit; 3 new tests |
| 6 | **The usage view and plans for people.** `GET /v1/billing/plans` (catalogue, current, effective with a seat, monthly usage), `GET /v1/settings/usage`, `POST /v1/billing/sales-inquiry` (stored, the owner told through `alerting`) | fastapi, python-doctor, api-design | The cabinet's types pass contract tests; prices in the account's currency **Done 2026-10-18:** `GET /v1/billing/plans` (plans on sale plus the person's own when no longer sold, monthly prices in the account's currency by country, else by home; the month's minutes), `GET /v1/settings/usage` (the week's tokens per tier, packs left, frontier models; packs to buy with step 11), `POST /v1/billing/sales-inquiry` (revision `d4a8b1f3e602`: `sales_inquiries` in the person's home, rate-limited, `billing.sales_inquiry.received` → alerting's notice with its runbook section); identity's profile contract gains the account's country; response keys checked against the cabinet's types; 3 new tests |
| 7 | **Monitors and the account toolset.** Leo's `account.get_plan` and usage (read); the inv-4 monitor declared; the slice's status → `blocked` on its payment provider credentials and wave 3 | fastapi, python-doctor, agent-architecture | promtool tests pass; the tool spec passes the model-facing test |
| 8 | **Payments core and TBank.** `transactions`; the provider port; TBank (Init with 54-FZ receipt, token signature, statuses); checkout, the one `confirm`, the webhook committing before it answers; reconciliation every minute | fastapi, python-doctor, api-design, resilience-failure, consistency-coordination, Docker ×4 | 20 concurrent confirmations grant once; a transaction killed before commit answers 5xx; `AUTHORIZED` grants nothing; a stale pending order is found by reconciliation |
| 9 | **CloudPayments and lava; routing.** Both adapters (HMAC, `Completed`; lava's key and its subscription feed), `payment_routes` with the admin's switch (BL-D1) | fastapi, python-doctor, resilience-failure | Each provider's recorded webhooks replay green; a zone with no enabled provider answers 503 |
| 10 | **Auto-renew and cards.** Consents (376-FZ), card binding, the hourly renewal sweep in three phases, notices and emails | fastapi, python-doctor, task-scheduling, consistency-coordination, Docker ×4 | No charge without consent and card; an unknown outcome is never retried; a price change stops auto-renew with its email |
| 11 | **Promo codes and packs at checkout.** Promo application and counting; `POST /v1/settings/usage/top-up`; the packs on sale in `GET /v1/settings/usage` | fastapi, python-doctor, api-design | A code used up between checkout and payment still pays without the discount; a zero-cost grant pays no reward; `GET /v1/settings/usage` lists the packs on sale in `frontier.packs` with prices in the account's currency (an empty list since step 6) |
| 12 | **Workspace seats and trials.** Workspace subscriptions, `SeatAllowance` bound with `trialing`, the trial's rules (once per person and per work domain, one trial workspace per person, ≤ 5 seats), prorated additions (BL-D7), suspension at the trial's end, 7 days of grace only after a failed renewal, the 90-day unpaid deletion with its warnings (the deletion itself through workspaces' step 11) (BL-D5); the workspace seat in `GET /v1/billing/plans`. *Unblocks workspaces' step 6* | fastapi, python-doctor, consistency-coordination, task-scheduling, Docker ×4 | inv-16 holds under concurrent joins and seat changes; a second trial for a person or a domain is refused; a trial ends in suspension the same minute; a failed renewal keeps 7 days; payment within 90 days resumes everything; `GET /v1/billing/plans` gives a member of a team workspace its `seat` and the seat's plan as `effective_plan_id` (`seat: null` and the own plan since step 6) |
| 13 | **Company invoices.** `org_invoices`, PDF, the admin's "paid" mark (BL-D6), `POST /v1/billing/workspaces/{id}/invoices` | fastapi, python-doctor, api-design, blob-store, Docker ×4 | An invoice is paid once whatever the repeats; payment, seats and audit commit together |
| 14 | **Refunds and Admin › Billing.** Refunds of the unused part through TBank and CloudPayments, lava's matched event (BL-D8); overview per currency, transactions, invoices; sales inquiries | fastapi, python-doctor, api-design | A refund returns only the unused days (used packs and minutes are kept), ends its days and reverses unused credits; sums never mix currencies; Admin › Billing lists sales inquiries with the work email, company and message, read in each person's home, and the runbook's `sales-inquiry-received` section points there instead of its SQL (since step 6) |
| 15 | **Referral and affiliate history.** Read-only tables for M1, the admin's payout list for the hand payments | fastapi, python-doctor, data-storage | M-4's formulas give the draft's balances |
| 16 | **Cabinet: Upgrade, Settings › Billing and Usage on the API**, mocks deleted, the portal as BL-D1 | the four Vercel skills, web-design-guidelines, react-doctor | Screens on real data in 16 languages; react-doctor 100; the cabinet's `WeeklyLimit.limit_tokens` is `number \| null` and Settings › Usage shows an unlimited tier (the API sends null since step 6) |
| 17 | **Cabinet: Admin › Plans and promo codes, Admin › Billing on the API** | the four Vercel skills, web-design-guidelines, react-doctor | No mock left for billing screens; react-doctor 100 |
| 18 | **Contract verification and staging.** The native `/auth/me` replays; test terminals of each acquirer on `shosai.tech` | fastapi, python-doctor | A test payment, a renewal and a refund pass on staging |

## 5. Documents to update on approval

All done on 2026-10-17 with the plan's approval:

- STATUS.md: billing `planned`; identity gains step 15 (disposable mail domains); M2 lists desktop releases with a stable device id.
- SLICE_MAP §4.2.3: three-part event names.
- ADR 0007 amended and ADR 0054 written.
- `frontend/docs/upgrade-api.md`, `settings-api.md` and two contract comments: Stripe replaced by the acquirers and the card-binding page of BL-D1.
- F6 plan: the `WEEK` spend period (BL-D4). workspaces plan: trials at join and the unpaid deletion (BL-D5). identity plan: step 15. ARCHITECTURE §8.1: workspace retention.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Acquirer credentials and test terminals are the owner's | Step 8 starts with TBank's test terminal; the slice is `blocked` on credentials after step 7 |
| E-4: v2's entitlements must equal the draft's for every migrated account | The draft's plans migrate as archived plans with their limits (BL-D2); M1 runs E-4 per account |
| lava's missing webhooks | Reconciliation and the subscription feed from step 9; the inv-4 monitor |
