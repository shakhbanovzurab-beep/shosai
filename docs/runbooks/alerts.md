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

## Tickets (§16.6)

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

## Heartbeat

<a id="watchdog"></a>
### Watchdog

Always firing; never sent to the chat. Alertmanager renews the external heartbeat with it every minute (F5-D2). When the heartbeat service alerts that pings stopped, Prometheus, Alertmanager or the host is down: start with `docker compose ps` on the host.
