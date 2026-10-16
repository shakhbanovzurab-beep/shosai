# alerting

Business events to the owner's monitoring chat through Alertmanager, with ids, amounts and a link to the account's card — never a name or an address. Decision: [ADR 0052](../../../../../docs/adr/0052-business-events-to-the-monitoring-chat-through-alertmanager.md); plan: [F5 §3.11](../../../../../docs/plan/packages/F5-observability.md).

## Kinds

| Event | Class | Runbook |
|---|---|---|
| `ai.user_spend.exceeded` (core's AI port) | ticket, silent | `user-spend-exceeded` |
| `identity.account.deleted` | notice, batched by kind for 5 min | `account-deleted` |

A new kind: a builder of its texts in `domain/alerts.py`, a handler and a subscription in `channels/subscriptions.py`, a section in [docs/runbooks/alerts.md](../../../../../docs/runbooks/alerts.md); the tests check that every kind has one.

## Flow

The subscription only queues `alerting.post_alert` in the delivery's transaction (§14 rule 1); the delivery mark makes a redelivered event queue nothing. The task posts to Alertmanager's v2 API with the labels `alertname`, `severity`, `kind`, `event_id`, `home`, `environment`; the event's id makes a repeated post the same alert. Alertmanager down → five deliveries in about a minute, then the dead letter, which pages.

## Settings

`ALERTING_ENABLED` (off by default; on in staging and production) and `ALERTING_ALERTMANAGER_URL` — `.env.example` section 2. The card links use `PUBLIC_BASE_URL`. Metric: `shosai_alerting_posts_total{kind, outcome}` with `accepted`, `unavailable`, `rejected`.
