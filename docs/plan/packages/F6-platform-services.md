# F6 — Platform services: package plan

Prompt: [prompts/F6-platform-services.md](../prompts/F6-platform-services.md). Status: [STATUS.md](../STATUS.md). Decision records: [ADR 0034](../../adr/0034-platform-services-in-core.md) (services in core), [ADR 0035](../../adr/0035-provider-cost-from-reported-usage-and-price-table.md) (price source), [ADR 0036](../../adr/0036-exchange-rate-owned-by-platform-services.md) (exchange rate).

The package builds the services every slice needs from its first step: the AI provider port with cost rows, spend control and per-user guards; email; the periodic-job registry; Jev decisions; the agent tool contract. It contains no feature behaviour beyond these services. Slice names follow [SLICE_MAP.md](../SLICE_MAP.md); its §7.1 changes to this plan were applied on 2026-10-13: the email suppression list and the unsubscribe and email-image routes, spend reports for studio.

**Re-planned on 2026-10-13** per the [F1 audit](../audits/F1-audit.md) §3.6 and the owner's decision OD-8: the parts that rested on the draft (F6-1 … F6-5) are derived again from the slice map and the new cabinet, and the cost dedup and the partition upkeep use core's primitives (F6-7, F1 audit steps 4–5). The owner confirmed the resulting decisions F6-D5 … F6-D8 the same day ([ADR 0041](../../adr/0041-platform-services-replanned-from-the-product.md)): **F6 has no admin HTTP route and every step needs only F1**; the plan has nine steps, and the dependency on `identity` is gone. AI cost rows are kept 5 years.

## 1. Facts this plan rests on

### 1.1 Inputs

| Source | Fact |
|---|---|
| F1, [F1 plan](F1-backend-foundation.md) | `CoreServices` and `FeatureParts` are how a slice receives clients and contributes parts (`core/features.py`); every role builds every slice. Tasks are `TaskDeclaration`s with deadline, queue and retry policy; ticks never overlap (`send_tick`); the scheduler process runs `ScheduledLoop`s only (§14 rule 10). Outbox events carry ids only; a subscription handler runs inside a transaction and makes no external call. One Valkey client per process without client retries; locks state their outage policy. `TenancyScope(home, user_id, org_id)`; `HomeTransactions.begin`. Model-facing English registry exists and is empty |
| Target architecture | §4.3 row "API, Workers → AI": connect 10 s, stream stall 45 s, 120 s per analysis call, one retry before the first byte, breaker per call kind, ≤ 3 attempts per stage with effect key, provider-wide semaphore in Redis, retry budget 20%. §8.1 "Cost": `provider_costs` monthly partitions, UUID + effect key, same key → no second row or debit, live capture batched every minute, kept 5 years (402-FZ), older partitions dropped (ADR 0041). §12: `schedule_runs.last_run_at`, a missed interval runs once; errands and proactive triggers as due rows. §13.2: Redis down → expensive AI fails closed, kill switch treated as engaged, unlimited meetings unaffected. inv-9, inv-13. §16.4 monitor "provider calls without a cost row". §16.5 dashboard per provider |
| Leo architecture | `decide` through OpenRouter's Decisions API, model `typesafe/jev-1.13`, contract test, one cost row per request, deadline per call (ADR 0026); breaker per (provider, model) with a same-tier fallback from the registry (§11.1); a turn reservation and a separate daily budget for background runs (§5.4); `core/agent_tools` and `FeatureParts.agent_tools` (ADR 0029); due-row sources for `errands` and `proactive_triggers` (§12) |
| D1, [contracts/draft](../../../contracts/draft/consumers.json) | `/v1/admin/costs/{summary,timeline}` and `/v1/admin/abuse`, `/{user_id}`, `/{user_id}/action` are class `web`, `/v1/admin/costs/{guard,kill-switch}` `unused`: nothing outside the draft depends on them, so the admin API is designed from the new cabinet (F6-D5). `GET/POST /v1/unsubscribe` and `GET /email/{name}` are `external` (links in emails already sent); by OD-2 external routes are not gated, F6 keeps them for the people who hold those links (F6-C21) |
| D3, [DATA_MAPPING.md](../DATA_MAPPING.md) §5.23, §7.1 | Today's mapping gives F6 `provider_costs` (transformed: monthly partitions), `abuse_states`, `abuse_events`, `voice_sessions`, `translation_session`, `error_logs`; Valkey spend counters re-seeded from `provider_costs` (E-3); `spend:global:kill` carried. F6-D8 proposes what v2 keeps of this; `exchange_rates` moves to F6 (ADR 0036) |
| [SLICE_MAP.md](../SLICE_MAP.md) §2.10, §4 (site), §7.1, §8.1 | Unsubscribe and suppression move to F6 (the E routes `GET/POST /v1/unsubscribe` and `GET /email/{name}`, links in emails already sent) and serve newsletters, which `support` keeps (SM-10); the admin AI models screen of `studio` shows spend today and this month, a forecast, tokens, a daily series per model and the OpenRouter credits; the new admin panel has no cost, abuse or kill-switch screen of its own; `identity`'s admin users screen searches, shows the account card, blocks and bans with refund (SM-12); every `/v1/admin/*` router checks one of six fixed operator roles (SM-12); the model registry, defaults and role assignments belong to `studio` (SM-5); `site` keeps the landing demo and the help-centre assistant (FM-1a, FM-1b), which call models without a user |
| [F1 audit](../audits/F1-audit.md) §3.6, steps 4–5 | Core now has the effect-key ledger (`core/idempotency`, `EffectLedger.once`, keys kept per scope up to 90 days) and monthly partitions (`core/db/partitions`, a policy per table, a daily upkeep tick per home); F6 builds on both instead of its own `provider_cost_effects` table and partition job |
| D4, [FEATURE_MAP.md](../FEATURE_MAP.md) | F6 owns `services/llm/` provider clients, cost and spend control, the abuse guard, `core/llm`, `api/ai/ws_metering.py`, `api/admin/{costs,abuse}.py`, `services/email/`, `tasks/send_email.py`, the periodic-job registry; draft specs 002, 008, 012, 016, 028 |

### 1.2 The draft, for lessons

Read in `/root/whisperer/backend/src/meetassist/` and `specs/`. Each lesson becomes a rule here.

| Draft fact or incident | Rule in v2 |
|---|---|
| ≈ 30 places create provider clients; 7 `LLMRouter()` call sites leak two HTTPX pools each (`services/notes_enhancer.py:243` and others); spec 028 tried a singleton | One port instance per process, built by composition; import-linter forbids provider SDKs outside `core.ai`; a source test forbids provider hosts outside it (ADR 0034) |
| No effect key or unique constraint on `provider_costs`; most callers swallow write errors without a log (`api/ai/proxy.py:91-119`, `stages.py:432-448`) | Effect key required on every call; one row per key by a dedup table in the same transaction; a failed write is deferred to a task, never swallowed, and counted |
| Calls with no cost row: meetings rerank, embeddings (no usage returned), memory summaries, proactive spoken text, a Gemini Live session, pyannote failures, the anonymous demo | Every operation of the port returns usage and writes its row; platform calls are charged to platform accounts; a failed paid call with reported usage is still recorded |
| Cost computed from a hard-coded table; unknown price → $0; cache discounts lost; 3.5 translate billed at 3.1's price | ADR 0035 |
| Reservations created but never settled or released; estimates counted twice in global counters (`router.py:347`, `spend_guard.py:248-265`) | A reservation has a lease and is settled or released by the port itself, never by the caller; global counters count actual cost once |
| Kill switch blocks only one legacy route; demo and docs assistant invisible to ceilings; Redis outage fails open everywhere (`spend_guard.py:457-520`) | One call class decides behaviour: `essential` never stopped by money (inv-13), `expensive` refused by the kill switch and when Valkey is down (§13.2); platform accounts have caps |
| Hard 402 for translation and subtitles on an exhausted premium budget, by a racy read | Ceilings are checked by one atomic script; what happens on refusal (fallback model or error) is the caller's route, not a hidden branch |
| Admin cost page summed only the calling admin's own rows (`api/admin/costs.py:78, 107, 255`) | Reports are platform-wide, per home, by an explicit query |
| Breaker per provider, on one call shape only; no paid-model fallback; spec 002's promised 429 retry never existed (`provider_breaker.py:17-22`) | Breaker per (provider, model) on every operation; same-tier fallback from the caller's route; retry rules of §4.3 in one place |
| Live-session pool fail-open, OpenAI Realtime without a pool (`live_capacity.py`) | Provider semaphore in Valkey for every provider; sessions hold a slot with a heartbeat |
| The abuse guard ran in shadow by default, its weights calibrated on the draft's traffic and prices; it mixed USD and tokens, counted background work as the user's, swapped transcription and images to a chat model, and its state machine carried audit bugs (`from_state`, `notified_at`, a row per active user) | No scoring at launch (F6-D6): hard per-user ceilings in USD, a concurrency cap and input caps stop what costs money now; only interactive calls count toward a user's caps; scoring is designed later from v2's own data |
| Abuse alert event carried the email (`domain_events.py:55`) | The spend alert event `ai.user_spend_exceeded` carries ids and numbers only (§12) |
| Email by f-strings and a `str.replace` chain: an event title containing `{body}` copied the body into the preheader (`templates.py:85-87`) | Templates rendered by Jinja2 with autoescape and strict undefined; slices own templates and texts |
| Emails enqueued before commit (auto-renew precharge, receipts, ticket reply) | A message is a row written in the caller's transaction; nothing is sent unless it commits |
| `retries=3` with a 60 s deadline gave at most 2 retries; no bounce handling; one SMTP connection per message | Retries are broker redeliveries (5 → 120 s backoff, 5 deliveries); 5xx is permanent and recorded; connections reused per worker within a short idle time |
| Language unset → Russian (`translate(None)`) | The caller passes the recipient's locale; fallback is English |
| Scheduler: no `schedule_runs`, no catch-up, "daily" sub-jobs ran on every deploy; `SCHEDULERS_ENABLED` default true; errand repair could run an errand twice | `schedule_runs` per home with a conditional claim; loops only in the scheduler (F1); due rows claimed with `FOR UPDATE SKIP LOCKED` by the slice's sweep |

### 1.3 Versions (2026-10-08)

| Package | Version | Use |
|---|---|---|
| httpx | 0.28.1 (already a dev dependency; becomes runtime) | OpenRouter, OpenAI REST, Deepgram, pyannote, Mistral OCR, Jev, CBR |
| websockets | 17.2 (§18.2 names 17.1 of 2026-09-30; latest stable at the time it is added) | OpenAI Realtime transcription and translation |
| google-genai | 2.29.0 (§18.2 names 2.25.0) | Gemini Live voice and translation |
| aiosmtplib | 5.1.3 | Async SMTP |
| jinja2 | 3.1.6 | Email templates |
| aiosmtpd | latest stable, dev only | In-process SMTP server for tests |

No `openai`, `deepgram-sdk` or `mistralai` SDK: the draft used none of them and the REST calls are small; HTTPX keeps one client and one timeout policy. Each step checks the version it adds against PyPI and the changelog.

## 2. Decisions

Confirmed by the owner on 2026-10-08:

| ID | Decision | Record |
|---|---|---|
| F6-D1 | Platform services live in `core` (`core/ai`, `core/email`, `core/schedule`, `core/agent_tools`, `core/exchange_rates`), passed through `CoreServices`; slices declare jobs and tools in `FeatureParts`; the admin API is a thin slice `features/ai_control` | ADR 0034 |
| F6-D2 | Cost = the provider's reported cost (OpenRouter, Jev), else units × a versioned price from the platform table `provider_prices` (EU home); OpenRouter prices synced daily; a model without a price is not called | ADR 0035 |
| F6-D3 | *Replaced by F6-D5:* the admin HTTP routes were F6's last step, built after `identity` | — |
| F6-D4 | F6 owns the Central Bank USD/RUB rate (`exchange_rates`, 6-hourly job, read port); `billing` reads it; `billing.refresh_rates` moves to F6 | ADR 0036; FEATURE_MAP §2.5 |

Confirmed by the owner on 2026-10-13 after the re-plan (OD-8), [ADR 0041](../../adr/0041-platform-services-replanned-from-the-product.md); F6-D6 and F6-D8 with the owner's changes, folded in below:

| ID | Question | Decision | Trade-off |
|---|---|---|---|
| **F6-D5** | The draft's admin routes for costs and abuse have no screen in the new cabinet (F6-1). Who serves the operator? | **F6 has no admin HTTP route.** Its operator functions are application services that the owners of the screens call from their own `/v1/admin/*` routers under SM-12's roles: `studio`'s AI models screen reads the spend reports, the credits and the forecast, and shows the kill switch with engage and release; `identity`'s account card reads one user's AI spend. Before `studio` ships, an operator engages or releases the kill switch with `shosai ai kill-switch engage --ttl 24h` (and `release`, `status`) on any backend container, or with `AI_KILL_SWITCH` at start. The email-link routes are public and move into the email step. `features/ai_control` is not built; ADR 0034 point 6 is amended | F6 no longer waits for `identity` and has nine steps; the kill switch has no button until `studio`'s admin step, only a command for whoever operates the servers. Owners' admin screens keep one router each, as SM-12 wants |
| **F6-D6** | The abuse guard copies the draft's scoring, calibrated on the draft's traffic (F6-2). What must be stopped at launch? | **Ceilings, caps and an alert; no scoring.** Money: the per-user daily and hourly ceilings by plan (from `billing`'s limits through `CallContext.spend_limits`), Leo's background budget, platform caps, the global ceilings and the kill switch (§3.6). Load: at most 2 interactive streams in flight per user (429 `rate_limited`); **meetings and standard transcription (`essential`) count toward the cap but are never refused** (owner). Size: input caps from settings (32 K tokens of context, 6 images ≤ 8 MB, values to revisit). Attention: `ai.user_spend_exceeded {user_id, spend_micro_usd, threshold_micro_usd}` once per user and day when a user passes `AI_USER_DAILY_ALERT_USD`; F5 alerts on it and an operator blocks through `identity`. `abuse_states`, `abuse_events`, the recompute job, cheap-model routing and the review queue are not built | Catches spend and load abuse with simple, testable rules; a slow, cheap automated user under every ceiling is not caught until v2 has data to score on (revisit when the alert or the cost reports show it). Removes ≈ 1 step and two tables |
| **F6-D7** | The base email layout is the draft's (F6-3) | **The layout comes from the cabinet's design system** (ADR 0022: its colour tokens, type scale, Shosai logo), keeping the technical rules: tables, inline styles, a dark-mode enhancement, RTL for `ar`, a plain-text part from the same template. The email step renders every kind in Mailpit in light and dark and the owner approves the screenshots before «Принято» | One design pass on email in the email step; the look matches the product instead of Whisperer's |
| **F6-D8** | Which draft data and Valkey keys v2 keeps (F6-5) | **Keep** `provider_costs` (the last 5 years, the retention the owner set for AI cost rows; older rows would be dropped at once) and `exchange_rates`. **Fold** `voice_sessions` and `translation_session` into `provider_costs` in M1: one row per session that has no cost row of its own, `cost_source = 'draft_session'`, effect key `draft:<table>:<id>`, so the money history is whole and v2 needs no session tables. **Drop** `abuse_states`, `abuse_events` (no scoring, F6-D6) and `error_logs` (provider errors are in logs and metrics now). **Valkey:** no draft key is carried; F6 provides `shosai ai rebuild-spend-counters` that recomputes today's, this hour's and this month's counters and the OCR page counters from `provider_costs` — run at cutover (E-3) and after a Valkey loss; the kill switch state is a runbook step of M2 (engage in v2 if engaged in the draft) | Less to migrate and verify; the counter rebuild doubles as recovery from an emptied Valkey (§13.2). Whitelists and appeal notes of the draft's abuse guard are lost; they have no use without it |

Design choices made in this plan, open to objection at plan review:

| ID | Choice | Why |
|---|---|---|
| F6-C1 | One row per effect key is enforced by core's effect-key ledger (`effect_keys`, F1 audit A9): the cost writer records each call through `EffectLedger.once` with the scope `ai.cost` (keys kept 35 days) and the outcome `{cost_id}`; the cost row and the settlements are the effect, so they are written once, in the same transaction | A unique index on the partitioned `provider_costs` would have to include the partition key and could not stop a replay that lands in the next month; the ledger is not partitioned. Every re-entry path (≤ 5 deliveries, ≤ 3 stage attempts, a 24 h `Idempotency-Key`) ends well within 35 days. No F6 table or purge job for it |
| F6-C2 | `provider_costs.user_id` is nullable with `payer` (`user`, `platform`) and `platform_account`; no foreign key to `users` | Calls without a user are charged to a platform account (prompt item 3); the row outlives account anonymisation (402-FZ, DATA_MAPPING) and `users` arrives with `identity` |
| F6-C3 | Credit debits are a **cost settlement hook**: a slice registers `CostSettlement`, called in the cost row's transaction only when the effect row was inserted; `billing` implements it with its ledger | inv-9's "at most one debit" follows from the same insert that makes one row; billing rules stay in `billing`; no event per cost row (≈ 43 rows/s of live capture would pass §12's 20 events/s trigger) |
| F6-C4 | Every call names a **call class**: `essential` (meeting capture, standard transcription and diarization, post-meeting analysis on the standard tier), `standard`, `expensive` (premium models, voice, translation, image generation, OCR beyond allowance) | inv-13 and §13.2 become one rule in one place: essential calls are metered but never refused by money, the kill switch or a Valkey outage; expensive calls fail closed |
| F6-C5 | Live streams accumulate usage in the process and write one cost row per (stream, minute) with effect key `stream:<id>:<minute>`, flushed as one multi-row insert per home per minute and at close | §8.1 "batched every minute"; a process crash loses at most one minute of cost rows for its streams, which the monitor's reconciliation shows |
| F6-C6 | A paid call whose cost row cannot be written (home down) queues `ai.record_cost` with the row; if Valkey is down too, the row is lost, logged and counted as `calls_without_cost_row` | The monitor of §16.4 counts exactly the calls that escaped; nothing is swallowed |
| F6-C7 | The port refuses a call of a Russian-home scope whose call context lacks the cross-border consent flag, with `consent_required` | nfr-14 at the one choke point every call passes; the consent itself is `identity`'s and `workspaces`' data, passed by the caller |
| F6-C8 | *Withdrawn by the re-plan:* the abuse guard's shadow mode (F6-D6) | — |
| F6-C9 | *Withdrawn by the re-plan:* the abuse guard's cheap-model routing (F6-D6) | — |
| F6-C10 | A transactional email is a row in `email_messages` written in the caller's transaction; a relay per home (every 2 s) queues `email.send` with the row id on `critical` (transactional) or `bulk` (newsletter); the worker renders and sends outside any transaction, then marks the row | Outbox semantics without personal data in Valkey or in events; a verification code leaves within ≈ 2 s of commit |
| F6-C11 | The sender mailbox is chosen by message kind: `account` (verification, reset, welcome) → the account mailbox, everything else → the notification mailbox; two SMTP accounts, as Timeweb requires `From` = login | The draft's routing (`services/email/routing.py:9-12, 65-89`) |
| F6-C12 | Tests send mail to an in-process `aiosmtpd`; development uses a Mailpit container in `compose.dev.yaml` | No network in tests; a developer sees rendered mail locally |
| F6-C13 | A periodic job is claimed by one conditional `UPDATE schedule_runs … WHERE last_run_at IS NULL OR last_run_at <= now() - interval RETURNING`, then queued with `send_tick`; a failed queue restores the previous `last_run_at`; a tick skipped because the previous run is still in flight keeps the claim, since that run is this interval's | Two racing ticks: one update wins (DoD); a missed interval is due once, never a backlog (§12) |
| F6-C14 | A due-row source is a scheduler tick per home that queues the slice's sweep task; the sweep claims rows with `FOR UPDATE SKIP LOCKED` in the worker | The scheduler only enqueues (§4.2); the slice owns its rows and their state machine |
| F6-C15 | Retry before the first byte covers connection failures and 429, 502, 503, 504 answered before any body byte; the retry budget is per process and provider: retries ≤ 20% of calls in a sliding 10 s window | §4.3; a per-process budget needs no shared state and bounds a storm from every process |
| F6-C16 | Breaker state per (provider, model) in Valkey: 5 failures in 30 s open it for 20 s, then one probe; failures are transport errors, 429, 5xx and stream stalls; with Valkey down each process keeps its own breaker | §4.2 places breaker state in Valkey; the local fallback keeps protection during an outage |
| F6-C17 | Metric labels: `provider`, `kind`, `call_class`, `outcome`; `model` only on breaker and cost-per-hour metrics, bounded by the price table's rows | §16.7: labels from closed sets |
| F6-C18 | `provider_costs` is partitioned by month through core (`register_monthly_partitions(MonthlyPartitions("provider_costs", ahead_months=2, keep_months=60))` in its migration); core's daily upkeep creates and drops its partitions | AI cost rows are kept 5 years (402-FZ, ADR 0041), with no F6 job (F1 audit A8) |
| F6-C19 | Platform accounts, derived from the slice map: `landing_demo` and `help_assistant` (`site`, FM-1a and FM-1b), `system` (platform work such as `studio`'s catalogue texts); each has daily and hourly caps from settings, and per-visitor caps stay in `site` | The new cut keeps both public AI features in `site`; no other slice calls models without a user (Leo's background runs are the user's, §5.4) |
| F6-C20 | The interactive-stream cap counts a user's open `stream_chat` calls and sessions of `origin = interactive` in a Valkey set with a heartbeat (as the semaphore, §3.5). An `essential` call or session joins the set and counts, but is admitted whatever the count; only `standard` and `expensive` calls are refused at the cap. With Valkey down the cap is not enforced and essential calls go on, others follow §3.6 | One structure for the semaphore and the cap; no cap and no Valkey outage ever stops a meeting or a standard transcription (inv-13, owner) |
| F6-C21 | Unsubscribe tokens of v2 are signed (HMAC-SHA256 with `EMAIL_LINK_SECRET`), name the home, the user and the kind, and do not expire. A token in an email the draft sent — `<user_id>.<first 32 hex of HMAC-SHA256(draft JWT secret, user_id)>` (`services/email/unsubscribe_link.py`) — is verified with `DRAFT_UNSUBSCRIBE_SECRET` until 24 months after cutover and suppresses `newsletter` in the RU home, where every migrated account starts (ADR 0004); after an account transfer the saga moves the row | People must be able to leave a mailing from any email they hold (38-FZ, GDPR); OD-2 does not gate external routes, so this is F6's own promise. The draft's secret is kept only for this check |

## 3. Design

### 3.1 Layout

```text
backend/src/shosai/
  core/
    ai/
      calls.py            CallContext, Payer, PlatformAccount, CallClass, EffectKey, ModelRoute, ModelRef
      requests.py         ChatRequest, ContentPart, ToolSchema, EmbeddingRequest, RerankRequest, ImageRequest,
                          TranscriptionRequest, DecisionRequest (choice, score, noul questions), OcrRequest
      results.py          ChatResult, ChatEvent, Usage, Embeddings, Ranking, GeneratedImage, Transcript,
                          Decision, OcrPages, errors (ProviderError codes)
      port.py             AiProviders: the facade slices call
      operations/         one module per operation: routing, admission, resilience, call, recording
      adapters/           openrouter_chat.py, openrouter_media.py, openrouter_decisions.py, openai_audio.py,
                          openai_realtime.py, gemini_live.py, deepgram.py, pyannote.py, mistral_ocr.py
      sessions/           TranscriptionStream, TranslationStream, VoiceSession; minute batching
      costs/              provider_costs model (monthly partitions), writer over the effect-key ledger,
                          deferred-record task, settlement hook
      pricing/            provider_prices model, price cache, estimate, OpenRouter price sync job
      spend/              Lua scripts, ceilings, reservations, kill switch, platform accounts, reports,
                          counter rebuild
      resilience/         deadlines, retry budget, breakers, provider semaphore
      guards/             interactive-stream cap, input caps, the daily spend alert
      telemetry.py        provider metrics, invariant counters
      settings.py         AI section of the settings
    email/                message model, port, templates protocol, layout (Jinja2), relay, SMTP sender, tasks,
                          suppression list, the email-link routes (unsubscribe, layout images)
    schedule/             PeriodicJob, DueRowSource, schedule_runs model, walker, loops
    agent_tools/          ToolSpec, ToolContext, EffectClass, Reversibility, CostClass, PlannedEffect, Preview, ToolResult
    exchange_rates/       exchange_rates model, CBR fetch job, ExchangeRates port
  entrypoints/cli.py      `shosai ai kill-switch {engage,release,status}`, `shosai ai rebuild-spend-counters`
backend/tests/
  doubles/                ScriptedProviders (transport double), CapturedEmail; used by every slice's tests
```

Module names are indicative; each file stays under 300 lines.

### 3.2 Boundaries

- New import-linter contracts: **provider SDKs only in `core.ai`** (`forbidden`: `google.genai`, `openai`, `deepgram`, `mistralai`, `websockets` from every package except `shosai.core.ai`); **light contracts** (`forbidden`: `core.agent_tools` and the value modules of `core.ai` import no FastAPI, Starlette, SQLAlchemy, redis, HTTPX, provider SDK).
- A source test fails when a provider host (`openrouter.ai`, `api.openai.com`, `generativelanguage.googleapis.com`, `api.deepgram.com`, `api.pyannote.ai`, `api.mistral.ai`) appears outside `core/ai`.
- `CoreServices` gains `ai: AiProviders`, `email: EmailPort`, `exchange_rates: ExchangeRates`. `FeatureParts` gains `periodic_jobs`, `due_sources`, `agent_tools`, `cost_settlements`.
- Core's own tasks and jobs (cost deferral, price sync, rate fetch, email relay and send, purges) are registered by composition like the outbox relay.
- The email-link routes are core's public router, included by the api role like `GET /v1/health`; F6 has no admin router (F6-D5).

### 3.3 Provider port

`AiProviders` operations, each taking a `CallContext` and returning usage with its result:

| Operation | Providers | Usage → cost |
|---|---|---|
| `chat`, `stream_chat` (tools, reasoning, vision parts, web search plugin) | OpenRouter | reported `usage.cost` |
| `embed`, `rerank` | OpenRouter | reported |
| `generate_image` | OpenRouter | reported |
| `transcribe` (file) | OpenRouter, OpenAI audio, Deepgram | reported (OpenRouter) or seconds × price |
| `diarize` | pyannote | seconds × price, also when the job fails after upload |
| `open_transcription_stream` | OpenAI Realtime | seconds × price, minute rows (F6-C5) |
| `open_translation_stream` | OpenAI Realtime translate, Gemini Live translate | seconds or tokens × price, minute rows |
| `open_voice_session` | Gemini Live | tokens per modality × price with the draft's wall-clock floor (32 tokens/s of input audio), minute rows |
| `ocr` | Mistral OCR | pages × price |
| `decide` | Jev via OpenRouter Decisions API, pinned `typesafe/jev-1.13` | reported, priced by input tokens; deadline from the caller |

`CallContext`: `scope` (home, user, org) or a platform account, `effect_key`, `feature` (closed label), `call_class`, `origin` (`interactive`, `background`, `system`), `deadline`, `spend_limits` from the caller (for example `billing`'s premium allowance), an optional open `SpendReservation` (a Leo turn), and the cross-border consent flag (F6-C7).

`ModelRoute`: the primary model and same-tier fallbacks, each `ModelRef(provider, model)`, chosen by the caller (`studio`'s model routes later); the port moves to the next model when the breaker of the current one is open or its call failed before the first byte.

One call goes through: validate (input caps) → consent → price check (ADR 0035) → admission (spend reservation, kill switch, interactive-stream cap) → semaphore slot → breaker → adapter with deadlines and retry → record (cost row, settlement, counters, spend alert, metrics) → result. Provider errors map to a closed set of codes (`model_unavailable`, `rate_limited`, `context_length_exceeded`, `content_refused`, `deadline_exceeded`, `spend_refused`, `kill_switch`, `consent_required`, `model_unpriced`, `provider_error`); model-facing error texts are English and registered.

### 3.4 Cost rows

- `provider_costs` in each home (platform calls in the EU home), monthly partitions on `created_at`, UUIDv7 `id`, primary key `(id, created_at)`; the draft's columns plus `effect_key`, `payer`, `platform_account`, `org_id`, `cached_tokens`, `cost_source` (`reported`, `priced`, `draft_session`), `price_id`, `call_class`, `origin`. Its migration registers the policy with core (F6-C18): two months ahead, 60 months kept (5 years, §8.1, ADR 0041); core's daily upkeep does the rest.
- One transaction per recorded call in the payer's home: `EffectLedger.once(session, EffectKey(AI_COST, effect_key), RecordedCost, effect)` where the effect inserts the cost row and runs the registered `CostSettlement`s (F6-C1). A replay with the same key returns the stored `cost_id` and changes nothing (inv-9; DoD test).
- The transaction runs after the provider call, never around it (§14 rule 1). F6-C6 covers a failed write.

### 3.5 Resilience

- Deadlines from §4.3: connect 10 s, stream stall 45 s, 120 s per analysis call (a caller may set less, `decide` always sets its own), realtime connect 3 s with one reconnect, phrase deadline max(15 s, 2 × duration).
- Retry before the first byte and the retry budget (F6-C15); breakers per (provider, model) (F6-C16); fallback along the `ModelRoute`; "model unavailable" only when the route is exhausted.
- Provider semaphore: a Valkey sorted set per provider with a member per call or session, heartbeat 30 s, stale after 120 s; limits from settings (OpenRouter in-flight 292 at the design point, realtime sessions below each provider's quota). Over the limit: `retry_later` for sessions, a bounded wait then `rate_limited` for calls. Valkey down: essential calls proceed without a slot (counted), others are refused.
- One HTTPX client per provider per process with explicit limits and keep-alive 120 s (draft lesson: cold TLS per question).

### 3.6 Spend control

- Money in integer micro-USD in Valkey; one Lua script checks and increments every applicable ceiling or none: the kill switch, the caller's limits (premium allowance, Leo's background budget per user per day, §5.4), platform-account caps, the global daily and hourly ceilings.
- Estimate = price × (input estimate + `max_output_tokens`) for token calls, price × reserved minutes for sessions (renewed per minute); a reservation has a lease and lives in a hash of reservation id → (µ$, expiry); the script ignores expired entries. The port settles on record (estimate replaced by actual once, keyed by the effect key) or releases on failure — callers never do.
- `SpendReservation` for a Leo turn: opened by the agent with an estimate for the turn, every call of the turn settles against it, closed at the end.
- Call classes (F6-C4): essential calls skip ceilings and the kill switch but are metered; when Valkey is down, expensive calls are refused (kill switch treated as engaged), standard and essential proceed and are counted.
- Kill switch: `AI_KILL_SWITCH` setting or a Valkey key with a TTL (default 24 h). Engaged: expensive calls refused, or the caller's route falls back to its standard model where it gives one. `KillSwitch.engage(ttl, reason)`, `release()`, `state()` are an application service: `studio`'s admin router calls it from the AI models screen, and the CLI `shosai ai kill-switch …` calls it before that screen exists (F6-D5). Every change writes one log line with the operator or `cli` and the reason.
- Platform accounts (F6-C19): `landing_demo`, `help_assistant`, `system`, each with daily and hourly caps from settings; their per-visitor caps stay in `site`.
- Reports (application services behind a `SpendReports` port): spend state against the ceilings, summary by provider, model or feature (day, month, all time), a daily series per model with tokens, a month-end forecast from the month so far, one user's spend today, this week and this month (for `identity`'s account card), and the OpenRouter credit balance (read from OpenRouter, cached 5 min) — platform-wide, both homes, RUB at each row's snapshot rate. F6 serves none of them over HTTP (F6-D5).
- Counter rebuild: `rebuild_spend_counters(home)` recomputes the day, hour and month counters, per user and global, and the OCR page counters from `provider_costs`, and writes them with one script; the CLI `shosai ai rebuild-spend-counters` runs it at cutover (DATA_MAPPING E-3) and after Valkey comes back empty (F6-D8).

### 3.7 Per-user guards

At launch abuse is stopped by rules that need no calibration (F6-D6); scoring waits for v2's own data.

- **Money:** the ceilings of §3.6 — per user by plan through `CallContext.spend_limits`, Leo's background budget, platform caps, global ceilings, the kill switch.
- **Load:** at most 2 interactive streams or sessions in flight per user (F6-C20); a third `standard` or `expensive` one is refused with `rate_limited` and its `Retry-After`. Meetings and standard transcription (`essential`) count toward the cap but are never refused. Background and system calls are not counted.
- **Size:** input caps from settings, checked before any provider is called: context tokens (32 K), images per call (6) and image size (8 MB). A refused input is `input_too_large`, a closed error code with an English model-facing text.
- **Attention:** when a user's spend today passes `AI_USER_DAILY_ALERT_USD`, the recording transaction writes the outbox event `ai.user_spend_exceeded {user_id, spend_micro_usd, threshold_micro_usd}` once per user and day (a Valkey `SET NX` marker with a TTL to the day's end); F5 turns it into an alert, and an operator looks at the account card and blocks through `identity`.
- **Revisit when** the alert or the cost reports show abuse the ceilings do not stop, or the share of spend by the top 1% of users grows past a threshold the owner sets.

### 3.8 Email

- `EmailPort.enqueue(session, message)` writes an `email_messages` row in the caller's transaction: recipient, locale, kind (`account`, `notification`, `newsletter`), template key, parameters, optional reply-to and unsubscribe URL, optional campaign key (unique per recipient, replaces the draft's 7-day Valkey mark). Fields marked secret (codes, reset links) are never logged or dead-lettered.
- Templates: a slice registers `EmailTemplate`s (key, Jinja2 body fragment, subject and preheader keys, its message catalog); rendering uses autoescape and strict undefined. The base layout comes from the cabinet's design system (F6-D7: colour tokens, type scale, the Shosai logo) with the technical rules of email — tables, inline styles, a dark-mode enhancement, RTL for `ar` — and the footer and support address from settings; the plain-text part is produced from the same template, not by stripping HTML.
- Relay per home every 2 s (F6-C10) claims queued rows with `FOR UPDATE SKIP LOCKED`, queues `email.send {home, message_id}` on `critical` or `bulk`; the worker loads the row, renders, sends with aiosmtplib through the kind's mailbox (TLS required in production), marks `sent` or `failed` with the SMTP code. 4xx and connection errors retry by redelivery; 5xx is permanent. Rows purged 7 days after a final state.
- Headers: `Message-ID` stable per row (a redelivery after a crash sends the same id), `Auto-Submitted`, `List-Unsubscribe` with `List-Unsubscribe-Post` for newsletters and notifications.
- **Suppression list** (SLICE_MAP §7.1): `email_suppressions` in each home, one row per (user, kind) the person unsubscribed from. `enqueue` skips a suppressed `newsletter` or `notification` message and counts it; the `account` kind (codes, resets, receipts) is never suppressed. Account deletion removes the person's rows with the rest of their data.
- **Links in emails** (email step): `GET /v1/unsubscribe` shows a confirmation page in the recipient's language, `POST /v1/unsubscribe` applies it (one-click per RFC 8058); tokens per F6-C21, the draft's included. `GET /email/{name}` serves the images of the new layout and the draft layout's images that emails already sent point at, from a fixed list, with long cache headers. Both are public and rate-limited with core's GCRA limiter.

### 3.9 Periodic jobs and due rows

- `PeriodicJob(name, every, task, homes)`: `task` is a tick declaration with a `HomeTaskPayload`; `homes` defaults to both, platform jobs name the EU home.
- `schedule_runs (job_name PK, last_run_at)` in each home (step 1 left out `last_task_id` and `updated_at`: nothing reads them, and the claim itself is the record). The scheduler checks due jobs every 5 s per home and claims each by F6-C13; jobs registered by slices and by core alike. A job unknown to the code is left alone; a job removed from the code keeps its row.
- `DueRowSource(name, every, sweep)` (F6-C14), used by `errands` and `proactive` (`proactive_triggers`); F6 provides the claim helper `claim_due(session, table, limit)` over `run_at` and `status` columns with `FOR UPDATE SKIP LOCKED`.
- Jobs of F6: price sync (daily, EU), rate fetch (6 h, EU), purge of `email_messages` (daily, both). The partitions of `provider_costs` and the cost keys of the ledger are kept by core's own ticks (F1 audit A8, A9).

### 3.10 Agent tool contract

`core/agent_tools` as ADR 0029 and Leo architecture §8.1 define it: `ToolSpec` (name, toolset, English description, Pydantic `input` and `output`, `effect`, `reversibility`, `cost_class`, entitlement and switch names, `result_budget`, `timeout`, `plan`, `preview`, `execute`, `invalidates`), `ToolContext` (principal ids, scope, deadline, trace, taint), `PlannedEffect`, `Preview` (i18n key and parameters), `ToolResult` (data or typed error). Validation rules are checked when a spec is built (namespaced name, ≤ 8 tools per toolset is checked by the agent's registry in `agent`). Composition collects `FeatureParts.agent_tools`; the model-facing English test walks every registered spec's description, schemas and enum values.

### 3.11 Telemetry

- Per provider: call count and latency histogram by `kind` and `outcome`, time to first byte, retries and retry-budget refusals, breaker state and transitions per (provider, model), semaphore occupancy and refusals, session pool occupancy, cost in µUSD by `provider` and `call_class` (cost per hour in Grafana).
- Invariant monitor (§16.4): counters `shosai_ai_calls_billed_total` and `shosai_ai_cost_rows_recorded_total` (rows written directly or by the deferred task, live rows count their calls) and `shosai_ai_calls_without_cost_row_total`; a reconciliation job compares billed calls per hour per home (Valkey counters) with rows in `provider_costs` and sets the monitor gauge. The alert rules are handed to F5.
- Spans per call with provider, kind, model, outcome; no prompt, text, audio or email address in spans or logs (§16.8).

### 3.12 Settings

New sections, each variable documented in `.env.example`: provider keys and base URLs; deadlines (only where §4.3 leaves a choice); semaphore limits per provider; global ceilings and platform-account caps; `AI_KILL_SWITCH`; the input caps and `AI_USER_DAILY_ALERT_USD`; `EMAIL_LINK_SECRET` and `DRAFT_UNSUBSCRIBE_SECRET`; the two SMTP mailboxes (`SMTP_ACCOUNT_*`, `SMTP_NOTIFICATIONS_*`); public base URL, support address; CBR URL. The production gate requires SMTP over TLS and every provider key of an enabled provider; a provider without a key is disabled explicitly (draft lesson: "presence of a key is not a decision").

### 3.13 Not in F6

Admin screens and their routes: the AI models screen with spend and the kill switch (`studio`), the account card, block and ban with refund (`identity` and `billing`) — they call F6's services (F6-D5); model registry, roles and defaults (`studio`); Jev policies and decision records (`decisions`); premium budgets, credits and their ledger, entitlements (`billing`); email templates and texts (each slice); newsletters, their audience and schedule (`support`); per-visitor caps of the demo and the help assistant (`site`); Grafana dashboards and alert rules (F5); the WS frames of live capture and voice (`capture`).

## 4. Steps

Every step leaves the project working: its tests pass, python-doctor prints 100, mypy strict, Ruff and `lint-imports` are clean, and after «Принято» it is committed, pushed and CI on `main` is green. Every step loads `fastapi` and `python-doctor`; steps touching retries, breakers or schedules also `resilience-failure` and `task-scheduling`; a step touching `compose.dev.yaml` loads the four Docker skills.

| Step | Content | Skills | Done when |
|---|---|---|---|
| 1 | **Periodic jobs and due rows.** `core/schedule`, `schedule_runs` in both homes, the walker in the scheduler, `FeatureParts.periodic_jobs` and `due_sources`, the claim helper, metrics | fastapi, python-doctor, task-scheduling | Two racing ticks queue a job once per interval in each home (DoD); a missed interval runs once after a restart, not as a backlog; a failed queue restores the claim; a due-row sweep claims each row once under concurrency. **Done 2026-10-13:** `core/schedule` — `PeriodicJob`, `DueRowSource`, `schedule_runs` (revision `7f9095f97350`, both homes), `ScheduleWalker` (one conditional update with `SKIP LOCKED`, ticks queued after commit, a failed tick gives its claim back, a skipped one keeps it), `claim_due` with a lease; `FeatureParts.periodic_jobs` and `due_sources`; start step `schedule` refuses unregistered or duplicate jobs; core's daily purges and partition upkeep moved from loops to periodic jobs (no re-run on deploy); 868 tests |
| 2 | **Provider port core and OpenRouter.** `core/ai` value types and `AiProviders`; OpenRouter chat, stream, vision, embeddings, rerank, image, web search; `provider_costs` registered for monthly partitions with core (F6-C18), cost dedup through the effect-key ledger (F6-C1), `provider_prices` with seeds; `core/exchange_rates` with the CBR job; cost writer, deferred-record task, settlement hook; transport test double `ScriptedProviders`; import-linter contracts and the host test; FEATURE_MAP §2.5 updated | fastapi, python-doctor | One call writes one cost row; a replay with the same effect key writes no second row and runs no second settlement (DoD); a call to an unpriced model is refused; reported and priced costs match their sources; SDK and host checks fail on a planted violation |
| 3 | **Speech, realtime and sessions.** OpenAI file and realtime transcription, realtime translation, Gemini Live voice and translation sessions, Deepgram, pyannote; minute batching of live rows (F6-C5); session double | fastapi, python-doctor, resilience-failure | A 3-minute stream writes 3 rows (one per minute) and none twice on a replayed flush; a failed pyannote job after upload is still recorded; each adapter is tested against a recorded or local fake server, no network |
| 4 | **Jev decisions and OCR.** `decide` through OpenRouter's Decisions API with the pinned model, contract test on the response shape, per-call deadline; Mistral OCR; daily OpenRouter price sync | fastapi, python-doctor | The contract test fails on a changed shape; a decision writes one row priced by input tokens; a deadline breach returns `deadline_exceeded` without a late row; the sync appends only changed prices |
| 5 | **Deadlines, retries, breakers, semaphore.** §3.5 in one pipeline for every operation; fallback along `ModelRoute` | fastapi, python-doctor, resilience-failure | One retry only before the first byte; retries above 20% are refused; a breaker opens per (provider, model) and the route falls back to the next model; the semaphore holds across two processes; Valkey down keeps essential calls going |
| 6 | **Spend control and the kill switch.** Estimate, reserve, settle, release; ceilings; turn reservation; background daily budget; platform accounts (F6-C19); kill switch service and the CLI `shosai ai kill-switch`; `SpendReports` with one user's spend; counter rebuild and its CLI | fastapi, python-doctor, resilience-failure | No ceiling or kill switch stops an essential call (inv-13); expensive calls fail closed with Valkey down; concurrent reservations never pass a ceiling; an expired reservation frees its amount; reports sum both homes; after Valkey is emptied the rebuild restores every counter to the sums of `provider_costs`; the CLI engages and releases the switch |
| 7 | **Per-user guards.** Interactive-stream cap (F6-C20), input caps, the daily spend alert event (F6-D6) | fastapi, python-doctor, resilience-failure | A third standard interactive stream of one user is refused with `rate_limited` while background calls pass; an essential stream is admitted with two others in flight and counts toward the cap; an input over a cap is refused before any provider is called; a user passing the alert threshold yields exactly one `ai.user_spend_exceeded` per day; a Valkey outage stops no essential call |
| 8 | **Email.** `core/email`, `email_messages`, `email_suppressions`, relay, SMTP sender with two mailboxes, the base layout from the design system (F6-D7), Jinja2 rendering, `CapturedEmail` double; the email-link routes `GET/POST /v1/unsubscribe` and `GET /email/{name}` (F6-C21); Mailpit in `compose.dev.yaml` and `development.md` | fastapi, python-doctor, Docker skills | A rolled-back transaction sends nothing; a committed one is delivered once to the in-process server with the right `From`; 4xx retries and 5xx is permanent; a parameter containing template syntax is escaped; a suppressed newsletter is skipped and counted, an `account` message to the same person is sent; a v2 link and a draft link both suppress the right (home, user, kind) once; the owner approves the rendered layout in light and dark |
| 9 | **Agent tool contract and telemetry.** `core/agent_tools`, `FeatureParts.agent_tools`, model-facing registration; provider metrics, invariant monitor and reconciliation job; backend README sections; STATUS `done` | fastapi, python-doctor | A spec with a non-English description fails the model-facing test; the contract imports no framework; the monitor reports a planted missing row and zero otherwise |

Step 10 of the earlier plan (admin HTTP routes after `identity`) is removed by F6-D5: the email-link routes moved into step 8, and the operator functions are services that `studio` and `identity` serve from their own admin routers.

## 5. Risks

| Risk | Handling |
|---|---|
| OpenRouter changes or drops `usage.cost` for a call kind | The adapter falls back to units × price and counts it (ADR 0035 revisit trigger) |
| Jev's alpha endpoint changes shape | Contract test in CI and a recorded fixture; the `decisions` policies run their fallbacks |
| Live-row batching loses a minute of cost on a crash | Bounded by design (F6-C5); the reconciliation shows the gap per hour |
| Valkey outage during a live meeting | Essential calls proceed without slots and ceilings and are still recorded (§13.2) |
| Abuse that stays under every ceiling goes unnoticed without scoring (F6-D6) | The daily spend alert, the cost reports per user and the revisit trigger of §3.7; scoring is designed on v2's data when they show it |
| Provider quotas for 2 600 sessions are not contracted (§22) | Semaphore limits are settings; the owner sets them when quotas are known |
| google-genai upgrades change Live config handling (draft: unknown keys silently ignored) | The adapter states the config it relies on in a test against the SDK's types |
