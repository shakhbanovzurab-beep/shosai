# ADR 0052 — Business events reach the monitoring chat through Alertmanager, without personal data

- **Status:** accepted by the owner on 2026-10-16 as F5-D5; recorded in F5 step 8, the step that builds it.
- **Packages:** F5 (observability); a new slice `alerting`; `identity` and core's AI port (the events it consumes).
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §5, §12, §14 rule 1, §16.4, §16.6; [F5 plan](../plan/packages/F5-observability.md) F5-D4, F5-D5, §3.11; [ADR 0051](0051-new-user-leads-to-telegram-with-clay-enrichment.md).

## Context

- The draft posted business notices (new users, payments, support tickets) straight to Telegram through its own Bot API client: names and emails in a chat, no batching, a second Telegram integration beside monitoring.
- F5 sends every alert through Alertmanager to one monitoring chat (F5-D4): pages with sound, tickets and notices silent, notices batched by kind.
- Two business events need the owner now: one person's AI spend for a day passed the threshold (`ai.user_spend.exceeded`, F6-D6) and a completed account deletion (`identity.account.deleted`).

## Decision

1. **A slice `alerting`** owns business alerts. It has no tables and no routes: one event subscription per kind and one task, `alerting.post_alert`.
2. **Through Alertmanager, not Telegram.** The task posts the alert to Alertmanager's v2 API; routing, batching, silences and the bot token stay in Alertmanager. The spend event is a `ticket`, a deletion a `notice` (batched for 5 minutes).
3. **No personal data.** An alert carries ids, amounts, a day and a link to the account's card in the admin panel — never a name, an email or a person's text. New users with names belong to `leads` and its own sales chat (ADR 0051).
4. **No external call in a transaction (§14 rule 1).** The subscription only queues the task in the delivery's transaction; the delivery mark makes a redelivered event queue nothing. The task posts outside any transaction.
5. **Once per event.** The event's id is a label of the alert, so a repeated post is the same alert to Alertmanager, which notifies once. The alert ends 30 minutes after the post: after the batching and the ticket's wait, never repeated.
6. **Failure is visible.** Alertmanager unreachable, too slow or answering 5xx earns another delivery, five in all (about a minute); then the task is dead-lettered and the dead-letter monitor pages (§16.4). A 4xx is a defect and is not retried.
7. **One switch.** `ALERTING_ENABLED` (off by default) and `ALERTING_ALERTMANAGER_URL` come from the environment; off, an event is accepted and logged and nothing is queued. Staging and production turn it on.

## Consequences

- Payments, support tickets and releases add their kinds to `alerting` with their slices: an event, a builder of the texts and a runbook section.
- The Telegram template shows each alert's card link; in a batch every item has its own.
- An Alertmanager outage longer than the retries leaves the alert in the dead letter, where an operator replays it; the page about the dead letter is delivered once Alertmanager is back.

## Revisit when

- Business notices grow into a stream the owner reads daily → a digest, or a separate chat for notices.
- The owner wants a person's details in a notice → that is `leads` (ADR 0051), not `alerting`.
