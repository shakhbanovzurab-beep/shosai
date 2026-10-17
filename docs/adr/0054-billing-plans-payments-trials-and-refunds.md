# ADR 0054 — Billing: acquirers, the catalogue, monthly minutes, tokens, trials, invoices, seats and refunds

- **Status:** accepted by the owner on 2026-10-17 (billing slice plan, decisions BL-D1 … BL-D8, five with the owner's amendments).
- **Packages:** `billing`; `identity` (disposable mail domains), `workspaces` (trials, unpaid deletion), `meetings` and `capture` (minutes checks), `agent` (the standard-model note), F6 (`WEEK` ceilings), the cabinet; M1 (archived plans), M2 (desktop releases with a device id).
- **Context documents:** [billing plan](../plan/slices/billing.md); [ARCHITECTURE.md](../design/ARCHITECTURE.md) fr-5, fr-15, nfr-10, inv-3 … inv-5, inv-13, inv-16, §8.1, §13.2, §22; [ADR 0007](0007-usage-tombstones-kept-for-lifetime-quota.md); [ADR 0053](0053-workspaces-access-rls-invitations-and-deletion.md).

## Context

The cabinet's billing screens were designed around Stripe, a monthly Free allowance, weekly tokens per tier and team plans per seat. The architecture, the draft's money flows and the shipped desktop clients use TBank, CloudPayments and lava.top, a lifetime Free quota, a USD budget for one plan and the draft's tariff shape. Trials, unpaid workspaces, invoices without a bank, seat changes and refunds had no rule.

## Decision

1. **Acquirers (BL-D1).** TBank and CloudPayments for roubles, lava.top with PayPal for other currencies, behind one provider port and chosen by the platform's payment routes. The cabinet keeps its redirect contract (`{url}`); adding a card is the acquirer's card-binding page; turning auto-renewal off is a switch in Settings. Stripe leaves the cabinet's documents.
2. **Catalogue (BL-D2).** The cabinet's plan model — slug, audience, seats, monthly and yearly prices in RUB, USD and EUR set by the admin and never converted, limits, capabilities. The draft's plans migrate as archived plans with their limits: a migrated subscription keeps exactly what it bought. The native clients' `TariffDTO` is derived from the plan.
3. **Free minutes (BL-D3).** 120 minutes a month on the Free plan; a deleted meeting's minutes stay counted in its month (ADR 0007 amended). Against abuse: an uploaded recording is checked against the minutes left before processing, and one longer than them is not processed — the person is offered a plan; at most one Free account per desktop device (the shipped clients' machine name at meeting start; the stable device id of the releases M2 waits for); registration refuses disposable mail domains (identity).
4. **Tokens (BL-D4).** Weekly token allowances per model tier; packs bought once, never expiring, spent after the weekly allowance; F6 gains a `WEEK` spend period. When the allowance and the packs are gone, Leo answers with a standard model without an error and notes briefly under the answer that the standard model answered because the limit is used up, with a link to the packs. The standard model has its own daily limit per plan through F6's ceilings; when it is used up the person gets a clear message, not unlimited use.
5. **Trials (BL-D5).** 14 days without a card; one trial per person for the account's lifetime and one per work mail domain; a person belongs to at most one trial workspace at a time; at most 5 seats and the limits of the ordinary paid plan. The owner is reminded in the cabinet 3 days and 1 day before the end. When the trial ends the workspace is suspended at once, with no grace. The 7 days of grace apply only to a failed renewal of a paid subscription. A suspended unpaid workspace is deleted after 90 days, with warnings to the owner 30, 7 and 1 day before; paying before then restores everything as it was.
6. **Invoices (BL-D6).** Invoices with their PDF from the start; the platform's admin marks one paid; matching by bank statement comes with the bank.
7. **Seats (BL-D7).** Added seats are paid at once for the rest of the period, by card or by a supplementary invoice; removed seats take effect at the next renewal.
8. **Refunds (BL-D8).** Through TBank's and CloudPayments' APIs; lava by hand in its dashboard, matched by its event. Only the unused part is returned — used packs and minutes are not — and a refund ends the days it paid for.

## Consequences

- identity gains a step: disposable mail domains refused at registration.
- workspaces: its join checks billing's trial rule (one trial workspace per person), and its deletion saga (step 11) also runs for a workspace billing scheduled after 90 unpaid days.
- meetings and capture read `MinutesAllowance`, including the pre-check of an upload's duration; the desktop device of a meeting reaches billing.
- agent shows the standard-model note; studio's models carry their tier.
- F6's ceilings gain `WEEK`.
- M2 lists desktop releases that send their stable device id at meeting start.
- ARCHITECTURE §8.1 (workspace retention) states the unpaid deletion.

## Revisit when

- Free accounts per device or per mail domain are evaded at a material rate → stronger device attestation.
- The bank for statements is chosen → the matcher replaces the admin's mark.
- A company needs a longer trial or more seats in it → a sales-led trial set by the admin.
