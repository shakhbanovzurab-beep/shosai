# Alerts runbook

Every alert Shosai sends to the monitoring chat links here ([target architecture](../design/ARCHITECTURE.md) §16.6). The message names the alert, its labels and a Grafana link; this page says what the alert means, where to look first and what usually fixes it. Classes ([F5 plan](../plan/packages/F5-observability.md), F5-D4):

- 🔴 **«Срочно»** (`page`) — people are affected now or an invariant is broken: an SLO's error budget is burning fast, or a monitor that must stay at zero is not. Act now. «✅ Всё снова в порядке» announces the end.
- 🟡 **«Нужно разобраться, не срочно»** (`ticket`) — a cause worth fixing in working hours. Silent, repeated daily while it lasts.
- 🔔 **«Событие»** (`notice`) — a business event for the owner (F5-D5). Silent.

The messages are plain Russian for the owner: what people experience, what it means, since when (Moscow time), a link here and, outside the developer's machine, to Grafana (`https://grafana.shosai.tech`). The headings below give each alert's technical name, which the chat does not show; the summary in the chat is the alert's `summary` annotation.

Staging commands run on the host in `/srv/shosai` as `sudo -u deploy docker compose …` ([staging runbook](staging.md)). Logs: Grafana → Explore → Loki, `{service="<service>"}`; a request by its id: `{service=~".+"} | request_id="…"`.

## Pages: error budget

<a id="slo-budget-burn"></a>
### SLO budget burn — `…BudgetBurnFast`, `…BudgetBurnSlow`, `…BudgetBurnTicket`

**Means.** The journey in the labels (`journey`, `slo`) fails or is slow more often than its objective allows (§16.3): *fast* — 2% of the 30-day budget in an hour, *slow* — 5% in 6 hours, *ticket* — 10% in 3 days. Objectives tracked, not paged (the Russian home's latency) arrive as tickets.

**Look.** The Grafana link opens the journey's dashboard. Find the failing route (5xx by `http_route`) or the slow one (p95 by route and home). Click an exemplar on the latency panel to open a slow or failed request's trace; from the trace, "Related logs" shows its lines.

**Fix.** A release just before the burn → roll back (`release.sh rollback`, [staging runbook](staging.md)). A dependency in the trace (a home's database, Valkey, a provider) → see its own alert. Latency in the Russian home only → the link to Russia, see [russian-home-link-slow](#russian-home-link-slow).

## Pages: invariant monitors (§16.4)

<a id="unknown-task-dropped"></a>
### UnknownTaskDropped — §14 rule 9

**Means.** A worker received a task whose name no process registers and dropped it: a producer is newer than the consumers, or a task was renamed.

**Look.** Logs of `workers-*`: the line names the task. `shosai_task_unknown_total` by `queue`.

**Fix.** Deploy the consumers before the producers (§17); if the release order was right, the task name changed without a compatibility alias — add it back.

<a id="outbox-event-stale"></a>
### OutboxEventStale — events delivered

**Means.** An event has waited in the outbox of a home for more than 5 minutes: the relay does not run or cannot queue deliveries.

**Look.** `shosai_outbox_oldest_age_seconds` by `home`; `scheduler` logs for `events.relay_outbox`; Valkey availability.

**Fix.** Scheduler down → start it. Valkey out of reach → restore it; the relay retries by itself. A delivery task missing from every worker → deploy the worker that has it.

<a id="dead-letter-present"></a>
### DeadLetterPresent — inv-8

**Means.** A task failed five deliveries and lies in a queue's dead letter. Nothing retries it.

**Look.** `shosai_task_dead_letter_entries` by `queue`; the dead letter in Valkey (`shosai:dead-letter:<queue>`) holds the task, its error and its trace id (secrets masked).

**Fix.** Fix the cause, then requeue or discard the entry deliberately; the page lasts while the entry is there.

<a id="provider-call-without-cost-row"></a>
### ProviderCallWithoutCostRow — inv-9

**Means.** A call to an AI provider finished without its cost row: spend is under-counted.

**Look.** `shosai_ai_calls_without_cost_row_total` by role and queue; logs around the time with the provider port's error.

**Fix.** A home that was out of reach when the row was written → the reconciliation fills nothing by itself; record the row from the provider's dashboard and fix the write path.

<a id="billed-call-without-cost-row"></a>
### BilledCallWithoutCostRow — inv-9

**Means.** The hourly reconciliation of a home found calls billed by the provider without a row in `provider_costs`.

**Look.** `shosai_ai_cost_rows_missing` by `home`; the reconciliation's log line names the hour.

**Fix.** As above; the gauge returns to zero at the next reconciled hour without a gap.

<a id="directory-entry-without-account"></a>
### DirectoryEntryWithoutAccount — inv-1

**Means.** The hourly check found directory entries (EU home) older than 10 minutes whose account is missing from the home they name. The address can neither sign in nor register again.

**Look.** `shosai_identity_directory_orphans` by `home`; the `workers-bulk` log line «В каталоге есть адреса без аккаунта в их доме» lists the first account ids. For each id, `directory_entries` in the EU home (state, home, `updated_at`) and `users` in the named home; `home_transfers` in both homes if a transfer ran.

**Fix.** An unfinished transfer → let its saga finish or cancel it (`/v1/admin/transfers/{id}`). An account erased by hand or by a faulty purge → mark the entry `deleted` so the address is free again. The gauge returns to zero at the next hourly check.

<a id="erasure-leftovers"></a>
### ErasureLeftovers — nfr-13

**Means.** After an account's erasure, an owner's own check found the person's data still there: rows, objects under a prefix, an external grant, a non-anonymised account or an address not freed.

**Look.** `shosai_identity_erasure_leftovers_total` by `handler`; the `workers-bulk` log line «После стирания у владельца остались данные человека» names the owner, the places (`remains`), the account id and the home.

**Fix.** Erase the named places for that account id, then fix the owner's `erase` so it covers them, with a test; a row written after the erasure by a late task means that task must check the account's state. The page ends 15 minutes after the last increase.

<a id="policy-disagrees-with-rls"></a>
### PolicyDisagreesWithRls — inv-14

**Means.** The hourly self-test, run as the sweep role (row-level security off), found workspace rows the access policy would show people outside the workspaces they belong to. Row-level security still hides those rows in requests, so nothing has leaked yet, but the policy — the first line — is broken.

**Look.** `shosai_workspaces_policy_rls_disagreements` by `home`; the `workers-bulk` log line «Политика доступа открывает строки вне пространств человека» with the count. Reproduce with the isolation kit (`tests/support/isolation.py`) on the resource of the last change; the policy's SQL is in `backend/src/shosai/features/workspaces/infrastructure/policy_predicates.py`.

**Fix.** Roll back the release that changed the policy or a slice's read path (§17 rollback), then fix the predicate with a test that fails on the case. The gauge returns to zero at the next hourly pass.

<a id="workspace-over-seats"></a>
### WorkspaceOverSeats — inv-16

**Means.** The daily check found workspaces whose active and hidden members plus pending invitations exceed the seats billing reports as paid.

**Look.** `shosai_workspaces_over_seats` by `home`; the `workers-bulk` log line «У пространства больше людей, чем оплачено мест» names each workspace id. Compare billing's seats of that workspace with its memberships and invitations.

**Fix.** A seat reduction applied without the membership check → restore the seats or ask the owner to remove members; a join that skipped the count → find the path in workspaces' `Admission` and fix it with a test. The gauge returns to zero at the next daily pass.

<a id="unrecorded-payment"></a>
### UnrecordedPayment — inv-4

**Means.** Reconciliation found a payment the acquirer reports as paid, and acknowledged by Shosai, with no committed transaction row (billing, from step 8). The person paid; what they paid for may not have been granted, and the money is not in the books.

**Look.** `shosai_billing_unrecorded_payments_total` by `home`; the reconciliation log line names the acquirer and its order id, never the person's data. Find the order in the acquirer's dashboard.

**Fix.** Record the payment through the one confirm path with the acquirer's order id (the confirm is idempotent), then check the person's subscription or packs. A repeat means the webhook answered before its commit: find the path and fix it with a test (nfr-10).

<a id="storage-counter-drift"></a>
### StorageCounterDrift — inv-11

**Means.** The daily reconciliation found people whose counted storage (`storage_usage.used_bytes`) differs from the sum of their visible personal files. The quota then refuses uploads it should allow, or allows bytes over the plan.

**Look.** `shosai_files_quota_drift` by `home`; the `workers-bulk` log line «Счётчик места расходится с файлами» lists the first account ids. For each id in that home: `storage_usage` against `SELECT sum(size_bytes) FROM storage_files WHERE user_id = … AND org_id IS NULL AND deleted_at IS NULL`, and the files changed recently (`created_at`, `deleted_at`).

**Fix.** Find the path that changed bytes without the counter (a claim, a copy, a deletion, a restore, the quota's removal) and fix it with a test; then set the person's `used_bytes` to the sum in one transaction. The gauge returns to zero at the next daily pass.

<a id="orphaned-object"></a>
### OrphanedObject — inv-11

**Means.** The daily reconciliation listed objects in a home's bucket under `u/` or `o/`, older than a day, that no file row names and no recorded deletion waits for. Nobody can reach them and the service pays for them.

**Look.** `shosai_files_orphaned_objects` by `home`; the `workers-bulk` log line «В бакете есть объекты без строки» with the count. List the bucket's prefix for the account ids in the keys and compare with `storage_files` and `object_deletions`; an upload rejected or swept while its object delete failed is the likely source.

**Fix.** Find the path that dropped a key without `object_deletions` and fix it with a test; then record the orphaned keys in `object_deletions` so the sweep deletes them. The gauge returns to zero at the next daily pass.

<a id="transcript-line-lost"></a>
### TranscriptLineLost — inv-6

**Means.** The settle sweep of an ended meeting found fewer live lines in the database than capture showed the person (meetings, from step 4). The person saw text that the notes, search and Leo will never get.

**Look.** `shosai_meetings_transcript_lines_missing_total` by `home`; the `workers-default` log line «Показанные строки не сохранены» names the meeting id and how many lines. Compare `transcript_segments` of that meeting (by `seq`, `origin = 'live'`) with capture's resume state for it; `shosai_meetings_transcript_lines_total{outcome="failed"}` and the drain's log show whether a batch failed, and a Valkey failover in the same minutes explains a lost second of queue (§20).

**Fix.** Find where the lines went — a failed batch not retried, a drain that dropped a batch, a queue lost with Valkey — and fix that path with a test. Lines that are gone cannot be recovered; the meeting's notes are written from what is stored.

<a id="meeting-left-unprocessed"></a>
### MeetingLeftUnprocessed — inv-7

**Means.** Meetings ended more than 15 minutes ago are still not settled (meetings, from step 4). Among them a spoken meeting may have no run, so its notes never come.

**Look.** `shosai_meetings_unsettled` by `home`; the task `meetings.settle_ended` in the workers' logs and its errors; `SELECT id, ended_at FROM sessions WHERE status <> 'active' AND settled_at IS NULL AND deleted_at IS NULL ORDER BY ended_at` in that home.

**Fix.** Make the sweep pass again: fix the failing task or the meeting row it stops at, with a test. The next pass settles the backlog oldest first, a batch a minute, and gives each spoken meeting its run; the gauge returns to zero.

## Tickets (§16.6)

<a id="meeting-run-old"></a>
### MeetingRunOld

**Means.** A home's oldest unfinished post-meeting run is older than 10 minutes (meetings, from step 5): a meeting's notes are late, and nfr-8 promises them within 10 minutes for 95 % of meetings.

**Look.** `shosai_meetings_oldest_open_run_seconds` by `home`; `shosai_meetings_stage_seconds` by stage for a slow stage; `shosai_meetings_runs_total` and the `workers-meeting` logs («Стадия прогона упала», «Стадия прогона провалена») for one that keeps failing; `shosai_task_queue_oldest_age_seconds{queue="meeting"}` for a queue that is behind; `SELECT id, source, state, stage_state, updated_at FROM meeting_processing_runs WHERE state IN ('pending', 'running') ORDER BY created_at LIMIT 20` in that home.

**Fix.** A stage slow at a provider: the provider's breaker and slots (`ProviderSlotsExhausted`); a queue behind: more `workers-meeting` processes; a stage failing for a bug: fix it with a test — the recovery sweep sends lost stages again every minute, and the attempts in each run's row keep it within three.

<a id="host-disk-filling"></a>
### HostDiskFilling

**Means.** A filesystem is more than 80% full (§14 rule 11). On staging Loki and Tempo have their own capped filesystems: one of them filling means its retention is too long for its volume.

**Fix.** `docker system df`; old images beyond the previous release; for a store's filesystem, shorten its retention or raise its cap (F5-D3).

<a id="database-pool-busy"></a>
### DatabasePoolBusy

**Means.** A process's connection pool to a home is more than 70% in use.

**Fix.** Long transactions (an external call inside one breaks §14 rule 1), or more load than the pool: check the transactions' spans, then the pool size against PgBouncer's limit (§14 rule 2).

<a id="provider-slots-exhausted"></a>
### ProviderSlotsExhausted

**Means.** Calls to a provider waited for a slot or were refused: its semaphore is full.

**Fix.** A slow provider holds slots longer — its latency panel; otherwise raise `<PROVIDER>_SLOTS` within the provider's quota.

<a id="task-queue-old"></a>
### TaskQueueOld

**Means.** The oldest task of a queue has waited more than 10 minutes.

**Fix.** Workers of that queue down or saturated: `docker compose ps`, their logs, task duration by name.

<a id="scheduler-loop-stalled"></a>
### SchedulerLoopStalled

**Means.** A scheduler loop has not finished successfully for three of its intervals (at least two minutes).

**Fix.** `scheduler` logs for the loop in `shosai_loop_name`; a home or Valkey out of reach stops loops that need it.

<a id="home-unreachable-from-app"></a>
### HomeUnreachableFromApp

**Means.** The application's processes cannot reach a home's database; requests of that home answer 503 `home_unavailable`. Tickets of the same home are muted meanwhile.

**Fix.** PgBouncer of that home (`pgbouncer-ru`, `pgbouncer-eu`), then the managed cluster in the provider's panel.

<a id="telemetry-dropped"></a>
### TelemetryDropped

**Means.** Log lines or spans were dropped on their way: a process's bounded queue, the collector's queue or memory limit, or Tempo refusing spans.

**Fix.** Loki or Tempo down or slow → see their targets; a flood of lines → find the service in Loki's volume panel; the collector's memory → its limit (F5-D3).

<a id="scrape-target-down"></a>
### ScrapeTargetDown

**Means.** Prometheus cannot scrape a target for 5 minutes.

**Fix.** The container of `job`/`instance` is down or unhealthy: `docker compose ps`, its logs.

<a id="role-missing"></a>
### RoleMissing

**Means.** No container of a Compose service (`service`) runs at all, so there is not even a target.

**Fix.** `docker compose up -d <service>`; if it exits at start, its last log line names the failed start step.

<a id="edge-health-failing"></a>
### EdgeHealthFailing

**Means.** `/v1/health` through the edge fails from inside the plane. The external probe (UptimeRobot) tells whether users see it too.

**Fix.** `edge` and `api` containers; the edge's error log in Loki.

<a id="certificate-expires-soon"></a>
### CertificateExpiresSoon

**Means.** The edge's certificate expires in less than 21 days: the renewal timer has not renewed it.

**Fix.** `systemctl status shosai-certificate.timer`; `deploy/certificate.sh` by hand ([staging runbook](staging.md)).

<a id="home-database-unreachable"></a>
### HomeDatabaseUnreachable

**Means.** A home's database host does not accept TCP connections from the plane.

**Fix.** The managed cluster's status in the provider's panel; the network path from the host.

<a id="russian-home-link-slow"></a>
### RussianHomeLinkSlow

**Means.** Connecting to the Russian home's database takes more than 250 ms for 15 minutes; Russian users' requests slow down with it (§20).

**Fix.** Usually the network between the EU plane and Russia; nothing to change in Shosai. Long-lasting → the revisit trigger of §19 (compute next to the Russian home).

<a id="edge-server-errors"></a>
### EdgeServerErrors

**Means.** The edge answered more than ten 5xx in five minutes (from its log).

**Fix.** 502/504 → `api`/`ws` down or slow; 500 from `api` → the API's error lines by `request_id`.

<a id="edge-rate-limiting"></a>
### EdgeRateLimiting

**Means.** The edge refused more than fifty requests in five minutes by its per-address limit (§4.3).

**Fix.** One address hammering the API — expected protection; a legitimate client — its retry logic; many addresses — an attack, the provider's firewall.

## Business events (F5-D5)

The slice `alerting` posts these to Alertmanager from events, not from Prometheus rules ([backend/src/shosai/features/alerting](../../backend/src/shosai/features/alerting)). A message carries ids, amounts and a link to the account's card in the admin panel — never a name, an address or a person's text. One event is one alert: its id is a label, so a redelivered event does not repeat the message.

<a id="user-spend-exceeded"></a>
### UserSpendExceeded — `ai.user_spend.exceeded`, ticket

**Means.** One person's AI spend for a UTC day passed `AI_USER_DAILY_ALERT_USD` (F6-D6; 20 $ by default). At most one message per person and day.

**Look.** The card in the admin panel (the link in the message): spend by day and by feature, sign-ins, devices. A steady climb over the day suggests a loop in a client or an agent; a burst from a new account suggests abuse.

**Fix.** Abuse → block the account on its card: its sessions end at once. A loop of ours → the feature's logs by `user_id` in Loki, then a fix. Legitimate heavy use → nothing; raise the threshold if this repeats for many people.

<a id="account-deleted"></a>
### AccountDeleted — `identity.account.deleted`, notice

**Means.** The erasure saga finished: a week after the person asked, every owner erased their data and the account is anonymised (identity, ADR 0045). Several deletions within 5 minutes arrive as one message.

**Fix.** Nothing to do. A deletion that does not finish is a separate alert of identity's monitors.

<a id="sales-inquiry-received"></a>
### SalesInquiryReceived — `billing.sales_inquiry.received`, notice

**Means.** A signed-in person sent the Enterprise form on the Upgrade page: a custom-priced plan for a team of the size in the message (billing, step 6). The work email, company and message are in `sales_inquiries` of the person's home, never in the chat.

**Fix.** Answer the person at the work email of the inquiry. Until Admin › Billing lists inquiries (billing step 14), read it in the person's home: `SELECT work_email, company, team_size, message, created_at FROM sales_inquiries WHERE user_id = '<id from the card link>' ORDER BY created_at DESC LIMIT 1;`.

## Heartbeat

<a id="watchdog"></a>
### Watchdog

Always firing; never sent to the chat. Alertmanager renews the external heartbeat with it every minute (F5-D2). When the heartbeat service alerts that pings stopped, Prometheus, Alertmanager or the host is down: start with `docker compose ps` on the host.
