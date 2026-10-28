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

**Leo's turn (`journey="leo_turn"`).** Failures: split `shosai_agent_turns_total` by `outcome`. `process_lost` — agent workers died or were killed mid-turn: check `RoleMissing` for `workers-agent`, its restarts and memory; `turn_deadline` — turns ran past 180 s, usually a slow model (`shosai_ai_call_duration_seconds` by model); `failed` — find "Ход Leo упал" in the agent worker's logs, with its stack. Overhead (the platform's own time, EU home): the worker's pickup (`shosai_agent_queue_pickup_seconds` — agent workers full or Valkey slow), then the trace of a slow turn: `agent.run` → `agent.context` and the final transaction around the model's `ai.call`.

**Leo's approved actions (`journey="leo_action"`).** `shosai_agent_approved_actions_total` by `result`: `late` — actions ended more than 30 s after their approval: the `agent` queue's age (`TaskQueueOld`), a slow slice's `execute` (`shosai_agent_action_execution_seconds`, the trace's `tool.<name>`), or the minute's sweep handing an unclaimed approval over again ("Одобренное действие снова не передано" in `workers-default`); `unknown` — an item's outcome nobody can tell: "Пункт действия Leo упал" in `workers-agent` with its stack, a slice's timeout, or an executor lost mid-action (the sweep's "Обход действий Leo").

**Leo's decisions (`journey="leo_decisions"`, tickets only).** `shosai_decision_requests_total` by `point`, `source` and `reason`, and the dashboard «Решения Leo: кто решает». `leo_decisions_zero_retention` — decisions refused with `not_zdr`: Jev's pinned endpoint left OpenRouter's zero-retention list or its status went three days unread; check the gauge `shosai_decision_zero_retention` and the `workers-default` log of the daily task `decisions.check_zero_retention` («Эндпоинт Jev вне списка нулевого хранения: решают правила», or «Статус нулевого хранения Jev не прочитан: решают правила» from the asking process), and read OpenRouter's `/api/v1/endpoints/zdr` by hand — while it lasts every point runs on its rules, which is safe; nothing to fix on our side unless the task itself fails. `leo_decisions_jev_on_time` — `reason="deadline"` above 5 % of asked decisions: Jev slow (`shosai_ai_call_duration_seconds{model="typesafe/jev-1.13"}`) or the process's in-flight cap (`shosai_decision_in_flight`); a late answer is still recorded (`shosai_decision_late_total`). `leo_decisions_fallbacks` — the rule stood in for more than a fifth of consulted decisions over three days: the dashboard's «Запасное правило: почему» names the reason; `no_consent` is expected for Russian-home people without cross-border consent and is not a fault.

## Pages: invariant monitors (§16.4)

<a id="decision-outcome-outside-bounds"></a>
### DecisionOutcomeOutsideBounds — ADR 0069

**Means.** A decision's changed outcome reached its caller other than as an active version's answer from Jev in time (`shosai_decision_outcomes_outside_bounds_total` by `point`) — for `voice.approval`, a spoken yes that would have carried out an action without the screen. This is the boundary of the owner's exception for voice approval (2026-10-27). The engine returned the rule's outcome instead, so nothing was approved; but some path produced a consent it must not.

**Look.** The counter's `point`; the log line «Исход решения вне границ: оставлено правило» in the asking process (`workers-agent` or the voice gateway) names the point; `shosai decisions report <point>` shows the versions in force.

**Fix.** Until the path is found, `shosai decisions retire voice.approval@<version>` turns voice approval off — every card is decided on the screen again. Then find where the engine returned a changed outcome without Jev's judged answer, with a test through `within_bounds`.

<a id="decision-unsafe-outcome"></a>
### DecisionUnsafeOutcome — ADR 0069

**Means.** A Decision Layer policy answered less carefully than its consumer's rule — for example a standard card where the agent's rule asked for a warning, or a toolset ranking that would drop a forced one (`shosai_decision_unsafe_outcomes_total` by `point`). The engine overruled the answer and kept the rule's outcome, so the person was protected; the policy version itself is broken and must not stay in force.

**Look.** The counter's `point`; `shosai decisions report <point>` names the version and revision in force; the log line «Политика смягчила исход правила» (in the process that asked: `workers-agent` for the agent's points) carries the point, never text.

**Fix.** `shosai decisions retire <point>@<version>` returns the point to its rule within a minute. Then fix the policy's `outcome` or `careful` in `features/decisions/domain/policies/`, with a Hypothesis test that no outcome is less careful than the rule, and release it as a new version through its gates and shadow.

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

**Look.** `shosai_notes_transcript_lines_missing_total` by `home`; the `workers-default` log line «Показанные строки не сохранены» names the meeting id and how many lines. Compare `transcript_segments` of that meeting (by `seq`, `origin = 'live'`) with capture's resume state for it; `shosai_notes_transcript_lines_total{outcome="failed"}` and the drain's log show whether a batch failed, and a Valkey failover in the same minutes explains a lost second of queue (§20).

**Fix.** Find where the lines went — a failed batch not retried, a drain that dropped a batch, a queue lost with Valkey — and fix that path with a test. Lines that are gone cannot be recovered; the meeting's notes are written from what is stored.

<a id="meeting-left-unprocessed"></a>
### MeetingLeftUnprocessed — inv-7

**Means.** Meetings ended more than 15 minutes ago are still not settled (meetings, from step 4). Among them a spoken meeting may have no run, so its notes never come.

**Look.** `shosai_notes_unsettled` by `home`; the task `notes.settle_ended` in the workers' logs and its errors; `SELECT id, ended_at FROM sessions WHERE status <> 'active' AND settled_at IS NULL AND deleted_at IS NULL ORDER BY ended_at` in that home.

**Fix.** Make the sweep pass again: fix the failing task or the meeting row it stops at, with a test. The next pass settles the backlog oldest first, a batch a minute, and gives each spoken meeting its run; the gauge returns to zero.

<a id="leo-item-executed-twice"></a>
### LeoItemExecutedTwice — L-N5

**Means.** The hourly check of the agent's audit trail found an item of an approved Leo action that a slice applied more than once under its key `action:index` (agent, from step 9a2): for example two identical tasks where the person approved one. The gateway marks an item `executing` before its slice runs and never retries it, and the slice applies a key once, so this should be impossible.

**Look.** `shosai_agent_items_executed_twice` by `home`; the `workers-default` log line «Пункты действий Leo исполнены дважды» names up to 20 action ids. For one of them: `SELECT event, item_key, tool_name, created_at FROM agent_audit WHERE action_id = '…' ORDER BY created_at` — two `executed` rows of one `item_key` show the slice that applied it twice (`tool_name`); the effect ledger's row for that key (`effect_keys`) shows whether the slice checked it.

**Fix.** Fix the slice's `execute` so the key is checked in the same transaction as the effect, with a test of two concurrent calls. Undo the duplicate for the person by hand only with their agreement. The gauge returns to zero once the rows are older than two hours.

<a id="leo-item-executed-unapproved"></a>
### LeoItemExecutedUnapproved — L-N5

**Means.** The hourly check found an item of a Leo action with an `executed` audit row but no `approved` row for its action (agent, from step 9a2): a change to the person's data that nobody approved. Only the Action Gateway executes items, and only after the conditional `proposed → approved` update that writes the `approved` row.

**Look.** `shosai_agent_items_executed_unapproved` by `home`; the `workers-default` log line «Пункты действий Leo исполнены без одобрения» names the action ids. `SELECT status, approved_at, approved_via FROM agent_actions WHERE id = '…'` and the action's audit rows; the slice named by `tool_name` and who sent its `agent.action_item.executed` (a write that bypassed the gateway, or an event with a forged key).

**Fix.** Stop the path that executes without the gateway — release a fix or switch the slice's write tools off — then tell the owner which people's data changed. The gauge returns to zero once the rows are older than two hours.

<a id="memory-written-while-off"></a>
### MemoryWrittenWhileOff — §16.4

**Means.** The hourly check found facts that a writer acting for the person — the admission after a turn, a meeting's recollections, Leo's tool — created after the person switched memory off (memory, from step 11). Leo remembers what the person told it not to. Every writer reads the switch in the transaction that writes, so this should be impossible; the person's own edits in Settings › Memory and the summary's box do not count.

**Look.** `shosai_memory_written_while_off` by `home`; the `workers-default` log line «Факты памяти записаны после выключения памяти» gives the facts' and the people's counts. In that home: `SELECT f.source_kind, f.source_ref, f.created_at, s.changed_at FROM memory_facts f JOIN memory_settings s USING (user_id) WHERE s.enabled IS FALSE AND f.created_at > s.changed_at AND f.source_kind NOT IN ('settings', 'user_edit')` — `source_kind` names the writer, and a run or meeting in `source_ref` leads to its task in the logs.

**Fix.** Find the writer that did not read the switch under the person's admission lock, fix it with a test of the switch turned off between the task's start and its write, and release. Forget the facts for the people concerned (`status = 'forgotten'`, `ended_reason = 'forgot'`) — the person chose that nothing be remembered. The gauge returns to zero at the next hourly check.

<a id="connector-secret-undecryptable"></a>
### ConnectorSecretUndecryptable — ADR 0075

**Means.** The weekly key pass (`connectors.rotate_keys`) found grant secrets in a home that no key of the Fernet ring opens. Those connections no longer work, and their people were not told.

**Look.** `shosai_connectors_undecryptable_secrets` by `home`; the `workers-bulk` log line «Секрет гранта не расшифровывается ни одним ключом кольца». Compare `FERNET_KEY` and `FERNET_KEYS_PREVIOUS` of the release with the last key change.

**Fix.** Put the removed key back into `FERNET_KEYS_PREVIOUS` and let the pass re-encrypt; remove an old key only after a full pass with `rotated=True` and zero lost. A ciphertext no key can ever open again is a lost grant: mark it `needs_reconnect` (`refresh_refused`) so the person is told. The gauge returns to zero at the next weekly pass.

<a id="connector-refresh-lost"></a>
### ConnectorRefreshLost — ADR 0075

**Means.** A provider rotated a grant's refresh token and the new one could not be written (three attempts inside the refresh lease). At providers whose old token dies on rotation (Atlassian, Notion, GitLab, Yandex), that grant is lost; it breaks at its next use and its person must reconnect.

**Look.** `shosai_connectors_refresh_lost_total`; the log lines «Новые токены не записаны» (the database error's class) and «Повёрнутый токен потерян» around the increase; the home's database health at that moment.

**Fix.** Repair what blocked the write (the home's pool, a lock, the database). Nothing can recover the token: the grant breaks with `refresh_refused` at its next refresh and the person is told once. The page ends 15 minutes after the last increase.

<a id="connector-client-misconfigured"></a>
### ConnectorClientMisconfigured — ADR 0075

**Means.** A provider's token endpoint refused Shosai's own OAuth application (`invalid_client`): its client id or secret is wrong, expired or revoked. Every grant of that application stops at its next refresh; no grant is marked broken, since the person cannot fix it.

**Look.** `shosai_connectors_client_misconfigured_total` by `client` (the application's key, e.g. `microsoft`); the log line «Провайдер отверг приложение Shosai». Check the application's secret in the provider's console — an Entra client secret expires after at most 24 months.

**Fix.** Issue a new secret, set `CONNECTORS_<KEY>_CLIENT_SECRET` and release. The page ends 15 minutes after the last increase.

## Tickets (§16.6)

<a id="meeting-run-old"></a>
### MeetingRunOld

**Means.** A home's oldest unfinished post-meeting run is older than 10 minutes (meetings, from step 5): a meeting's notes are late, and nfr-8 promises them within 10 minutes for 95 % of meetings.

**Look.** `shosai_notes_oldest_open_run_seconds` by `home`; `shosai_notes_stage_seconds` by stage for a slow stage; `shosai_notes_runs_total` and the `workers-meeting` logs («Стадия прогона упала», «Стадия прогона провалена») for one that keeps failing; `shosai_task_queue_oldest_age_seconds{queue="meeting"}` for a queue that is behind; `SELECT id, source, state, stage_state, updated_at FROM meeting_processing_runs WHERE state IN ('pending', 'running') ORDER BY created_at LIMIT 20` in that home.

**Fix.** A stage slow at a provider: the provider's breaker and slots (`ProviderSlotsExhausted`); a queue behind: more `workers-meeting` processes; a stage failing for a bug: fix it with a test — the recovery sweep sends lost stages again every minute, and the attempts in each run's row keep it within three.

<a id="host-disk-filling"></a>
### HostDiskFilling

**Means.** A filesystem is more than 80% full (§14 rule 11). On staging Loki and Tempo have their own capped filesystems: one of them filling means its retention is too long for its volume.

**Fix.** `docker system df`; old images beyond the previous release; for a store's filesystem, shorten its retention or raise its cap (F5-D3).

<a id="host-memory-low"></a>
### HostMemoryLow

**Means.** Less than 10% of the host's memory has been available for 10 minutes. Staging, its observability, LiveKit and the local development stack share this machine; under heavy pressure it has reset itself before.

**Look.** `docker stats --no-stream` for the containers using the most; `free -m` for swap; the `node` dashboard in Grafana for when it started.

**Fix.** A local development stack or a manual check left running: stop what you started. A container at its limit for good: its own ticket (`LiveKitMemoryHigh`, `EgressMemoryHigh`). Steady growth with every container within its limit: the host needs more memory, or the plane's limits are revisited (meetings plan §1.3).

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

<a id="leo-toolset-loads-frequent"></a>
### LeoToolsetLoadsFrequent

**Means.** In more than 5 % of the day's Leo turns the model called `core.load_toolset`: routing (ADR 0068 AG-D7) left out a toolset the question needed, so the turn paid an extra round of the model. Answers are slower and cost more; nothing is lost.

**Fix.** Read which toolsets runs loaded and on which pages: `agent_runs.routing` keeps `selected`, `deferred` and `loaded` per run. A page that should bring a toolset → add its section to the surface map in `features/agent/application/tool_offer.py`; segment 2 too full to hold the toolsets turns need → shorten the largest schemas or descriptions of the slice that owns them.

<a id="memory-admission-slow"></a>
### MemoryAdmissionSlow

**Means.** For half an hour 5 % of Leo's turns took memory more than a minute to read after the answer ended (`shosai_memory_admission_lag_seconds`, memory step 11). The quiet "Leo may remember" line under the answer comes late and new facts reach answers later; nothing is lost.

**Fix.** The task `memory.admit_turn` waits in the `default` queue → see [TaskQueueOld](#task-queue-old) and the workers' count: one `default` worker admits about 2.6 turns a second while the model answers in 1.8 s (memory step 11), and memory alone needs two of them at 10 000 DAU's peak; the model call is slow → the `ai.call` spans of the task's traces and `shosai_ai_call_duration_seconds` by `provider`, with `MEMORY_FALLBACK_MODEL` as the switch; the person's admission lock is held long → a meeting's recollection or the upkeep of the same person in the workers' logs.

<a id="memory-extraction-failing"></a>
### MemoryExtractionFailing

**Means.** More than 5 % of memory's model calls in half an hour — a turn's extraction or a meeting's recollections — ended in failure (`shosai_memory_extractions_total{outcome="failed"}` by `source`: `turn` or `meeting`; memory step 11). The tasks are retried, but what a person asked Leo to remember may be lost once the retries run out.

**Fix.** `shosai_ai_calls_total` and `shosai_ai_calls_refused_total` show whether the provider fails, refuses for the budget or times out; an unreadable answer twice in a row shows as `memory.extract` errors in the workers' logs — a model change behind `MEMORY_MODEL` is the usual cause; switch to `MEMORY_FALLBACK_MODEL` while it is fixed.

<a id="memory-candidates-turned-down"></a>
### MemoryCandidatesTurnedDown

**Means.** Over four weeks fewer than 70 % of people's answers to "Should Leo remember this?" were Remember (`shosai_memory_candidates_total{answer}` by `source`, at least 100 answers; MM-D1). Leo proposes what people do not want kept and spends their attention on it. The draft's carried-over candidates are left out: turning them down as a list says nothing about what Leo proposes.

**Fix.** Compare `source="user_statement"` with `source="meeting"`: one source turned down far more often points at its prompt (`extraction_prompts.py`). Read the turned-down statements of the staging accounts, not people's, and tighten what the prompt calls durable; the decisions slice's `memory.admit` calibration (MM-D1) is the lasting answer.

<a id="studio-catalogue-refresh-stale"></a>
### StudioCatalogueRefreshStale

**Means.** For two days no refresh of studio's catalogue finished (`shosai_studio_catalogue_refresh_total{outcome="done"}`): either OpenRouter's model list could not be read (`outcome="unreadable"`) or it missed a fifth of the catalogue and was not believed (`outcome="fused"`, ADR 0074). Models keep yesterday's description; nothing is switched off and no tier is proposed.

**Fix.** The worker's logs of `studio.refresh_catalogue` in Loki: an unreadable list → OpenRouter's status and the outbound route from the plane; a fused one → compare the catalogue with `GET https://openrouter.ai/api/v1/models` by hand. The next daily run repeats by itself.

<a id="studio-default-broken"></a>
### StudioDefaultBroken

**Means.** A role's default or fallback cannot answer (`shosai_studio_broken_defaults_total{reason}`): OpenRouter no longer lists its model (`unlisted` — the model stays on, since a default is never switched off by the refresh), or its model no longer reads what the role needs (`cannot_serve`). The role answers with its fallback, or answers `model_role_unconfigured` when neither can.

**Fix.** Admin › AI models: choose another default (and fallback) for the role; then the old model can be switched off. A renamed model → add its new id first.

<a id="studio-tier-proposal-waiting"></a>
### StudioTierProposalWaiting

**Means.** A tier the price proposed has waited for the admin for over three days (`shosai_studio_waiting_tier_proposals_total`, ST-D4 as amended). Until it is decided the model counts in its old tier: a model priced as frontier may still draw on people's standard tokens, at the platform's cost.

**Fix.** Admin › AI models: confirm or decline the proposal. A default cannot be made frontier: set another default first.

<a id="studio-role-unconfigured"></a>
### StudioRoleUnconfigured

**Means.** A role's requests are refused with `model_role_unconfigured` (503) because neither its default nor its fallback can answer (`shosai_studio_role_unconfigured_total`, studio plan §3.3): no default was set, or both were switched off, retired or stopped reading what the role needs. People in that role get an error instead of an answer.

**Fix.** Admin › AI models: set the role's default (a standard model that reads what the role needs) and a fallback. The ticket clears 15 minutes after the last refusal.

<a id="studio-substitutions-high"></a>
### StudioSubstitutionsHigh

**Means.** Over an hour, more than 5 % of a role's resolutions (at least 20) answered with the role's default instead of the model people chose, for one `reason` (`shosai_studio_route_substitutions_total`, by `studio_role`): `disabled` or `not_listed` — the operator switched off or retired a model people use; `cant_do_role` — a model stopped reading what the role needs; `not_on_plan` — people kept a frontier choice after their plan lost frontier models; `frontier_allowance_used` — frontier weeks run out, as billing allows (BL-D4).

**Fix.** For `disabled` and `not_listed`, switch the model back on or accept it: people keep the default until they pick again in Studio. For `cant_do_role`, check the model on the AI models screen. `not_on_plan` and `frontier_allowance_used` follow the plans; raise them with the owner if they last.

<a id="call-entry-failing"></a>
### CallEntryFailing

**Means.** A probe of a call's way in fails from inside the plane for 3 minutes (meetings A15): `rtc_signal` — `https://rtc.shosai.tech/` through the edge does not get LiveKit's answer, so nobody new joins a call; `turn_tls` — `turn.shosai.tech:443` does not accept TLS, so people behind networks that block UDP cannot connect.

**Look.** `docker compose ps livekit egress livekit-redis` in `/srv/shosai`; `docker compose logs --tail 100 livekit`; the edge's error log in Loki (`{service="edge"} |= "rtc"`); `openssl s_client -connect turn.shosai.tech:443 -servername turn.shosai.tech </dev/null` for the certificate's names.

**Fix.** LiveKit down: `docker compose up -d livekit`, then `docker compose restart egress` so egress joins its network namespace again (calls in progress are already gone). Both probes failing with the cabinet up: the certificate lacks the names — `sh /srv/shosai/deploy/certificate.sh expand /srv/shosai`. Only `turn_tls`: the edge's `SHOSAI_TURN_SERVER_NAME` is empty — re-render the environment ([staging runbook](staging.md#change-a-setting-or-a-secret)).

<a id="livekit-memory-high"></a>
### LiveKitMemoryHigh

**Means.** LiveKit's resident memory has been above its Go soft limit (`GOMEMLIMIT`, 90% of the container's hard limit) for 10 minutes: the garbage collector no longer keeps it down, and at the hard limit the kernel kills it with every call on it.

**Look.** The admin's LiveKit screen (rooms, participants, tracks); `livekit_participant_total` and `livekit_room_total` in Prometheus; whether rooms stay open after their people left (the sweep, `shosai_meetings_sweep_rooms_total`).

**Fix.** More calls than staging's ceiling allows means the ceiling is not applied: check `MEETINGS_ROOM_PARTICIPANTS_CEILING`. Memory growing with few rooms: a LiveKit leak — restart it between calls (`docker compose restart livekit`, then `docker compose restart egress`) and record the version. A real need: raise the limit and `GOMEMLIMIT` together in `deploy/staging/compose.yaml` and `MEETINGS_LIVEKIT_MEMORY_LIMIT_MB` in `livekit_files.py`.

<a id="egress-memory-high"></a>
### EgressMemoryHigh

**Means.** Egress has held more than 90% of its 1 GiB limit for 5 minutes. A recording in progress dies if it reaches the limit.

**Look.** `livekit_egress_proc_rss_bytes` for the processes inside it; the running recording's preset (A7b measured ≤ 434 MiB at 540p 15 fps).

**Fix.** A preset heavier than 540p 15 fps: return to it. Memory left after recordings ended: `docker compose restart egress` when no recording runs (`MEETINGS_RECORDINGS_CONCURRENT` is 1 on staging).

<a id="livekit-subscriptions-high"></a>
### LiveKitSubscriptionsHigh

**Means.** LiveKit has held more track subscriptions than 70% of its node's capacity for 10 minutes — 180 per core (meetings plan §1.3), the cores being LiveKit's `GOMAXPROCS`. Beyond the capacity forwarding falls behind and video stutters for everyone on the node.

**Look.** The admin's LiveKit screen: rooms, participants and tracks per node; `livekit_track_subscribed_total` by `kind`; whether video plays only for the people speaking (MR-D2) or every tile subscribes.

**Fix.** A few large calls: expected — more cores for LiveKit. Every tile subscribing to video: the cabinet's visible-tiles rule regressed (A10). On staging the threshold is never reached: its ceiling is 4 participants.

<a id="livekit-webhooks-rejected"></a>
### LiveKitWebhooksRejected

**Means.** More than 1% of LiveKit's webhooks in 15 minutes (and at least three) failed signature verification. Calls do not open and close in Shosai, or someone posts forged events to `/v1/livekit/webhook`.

**Look.** The `api` logs for «Вебхук LiveKit отклонён» and its `reason` (`body_hash_mismatch`, or the verifier's error); whether LiveKit's `webhook.api_key` in `secrets/livekit.yaml` matches `LIVEKIT_API_KEY` in `.env.staging`.

**Fix.** Keys differ: re-render the environment and recreate `livekit` and the roles together. Forged posts from outside: nothing breaks — they are rejected; the edge's rate limit holds them.

<a id="recordings-failing"></a>
### RecordingsFailing

**Means.** More than 5% of the recordings that ended in 15 minutes failed (`shosai_meetings_recordings_total` by `outcome`): people pressed Record and got no file.

**Look.** The outcome label: `start_refused` — egress refused or was unreachable at the start (its CPU accounting, `cpu_cost`, against its limit; `docker compose ps egress`); `egress_failed` or `egress_aborted` — egress's own log (`docker compose logs --tail 200 egress`), often the bucket (credentials, endpoint) or Chrome; `egress_lost` — `RecordingEgressLost`.

**Fix.** Egress down: `docker compose up -d egress`. A bucket error: the home's `HOME_*_S3_*` and `MEETINGS_EGRESS_S3_ENDPOINT_*` settings. Refusals at the start with egress up: its `cpu_cost` against its CPU limit (meetings plan §1.3).

<a id="recording-egress-lost"></a>
### RecordingEgressLost

**Means.** The sweep found a recording that its row says is running but LiveKit no longer knows, with no end reported (§3.7: a recording active without egress). It was marked failed with `egress_lost`; its file will not come.

**Look.** Whether egress or LiveKit restarted at that time (`docker compose ps`, their logs): recreating either drops what they held.

**Fix.** Recreate LiveKit and egress only when no call or recording runs ([staging runbook](staging.md#calls-livekit)). Repeated losses without restarts: egress's log around the recording's start.

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

**Means.** One person's AI spend for a business day (Moscow time by default, `BUSINESS_TIME_ZONE`, ADR 0058) passed `AI_USER_DAILY_ALERT_USD` (F6-D6; 20 $ by default). At most one message per person and day.

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

<a id="studio-model-unlisted"></a>
### StudioModelUnlisted — `studio.model.disabled`, ticket

**Means.** The daily refresh did not find a catalogue model in OpenRouter's list and switched it off (studio, ADR 0074). People who chose it answer with their role's default; nobody's settings change. A model switched off by the admin sends no message.

**Fix.** A renamed model → add its new id on Admin › AI models and switch it on; people choose it again themselves. A model gone for good → nothing; retire it on the same screen once no default holds it.

<a id="studio-tier-proposed"></a>
### StudioTierProposed — `studio.model.tier_proposed`, ticket

**Means.** A model's output price in force crossed `STUDIO_FRONTIER_OUTPUT_USD_PER_M` (6 $ per million tokens by default): its price proposes the other tier. Nothing changes until the admin decides (ST-D4 as amended); tokens already counted stay in their old tier.

**Fix.** Admin › AI models: confirm the proposal — the model counts in its new tier from that moment — or decline it, and it is not proposed again while the price stays on the same side of the line.

## Heartbeat

<a id="watchdog"></a>
### Watchdog

Always firing; never sent to the chat. Alertmanager renews the external heartbeat with it every minute (F5-D2). When the heartbeat service alerts that pings stopped, Prometheus, Alertmanager or the host is down: start with `docker compose ps` on the host.
