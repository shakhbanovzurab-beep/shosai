# F6 — Platform services

> **Planned and re-planned.** The package plan (`docs/plan/packages/F6-platform-services.md`), re-planned on 2026-10-13 per [ADR 0041](../../adr/0041-platform-services-replanned-from-the-product.md), governs where it differs from this prompt: no admin HTTP route (item 4's admin API), ceilings and caps instead of the abuse guard's scoring (item 4), the email layout from the design system (item 5), and five-year retention of AI cost rows.

Follow the common protocol in `docs/plan/prompts/README.md`. Load the `fastapi` skill before reading the draft or designing anything; load `resilience-failure` and `task-scheduling` for items 2 and 6.

**This package is multi-session.** Work in the session mode described in `docs/plan/prompts/README.md`; the package plan is `docs/plan/packages/F6-platform-services.md`. The planning session settles both ADR decisions below with the user first, because every step depends on them. A split that fits the work below — adjust it in the plan if the design needs another order:

1. Provider port with cost rows and effect keys, its test double (items 1, 8).
2. Deadlines, retries, breakers and the provider-wide semaphore (item 2).
3. Spend control and the kill switch (item 3).
4. Abuse guard and the admin API for costs and abuse (item 4).
5. Email port, SMTP sender, base layout and its test double (items 5, 8).
6. Periodic-job registry and the scheduler walk over both homes (item 6).
7. Provider telemetry and the "calls without a cost row" monitor (item 7).

## Goal

The services that many slices need from their first step, so that no slice waits for another: the AI provider port with cost rows, spend control and the abuse guard; email; the periodic-job registry. The user decided this package in D4 (`docs/plan/FEATURE_MAP.md`, decision FM-4). No feature behaviour beyond these services.

## Read first

- CLAUDE.md in full; target architecture §4.3 (rows "API, Workers → AI" and "Scheduler → Valkey"), §8.1 (entities "Cost", "Errand and schedule" and the Leo rows), §9 (inv-9, inv-13), §12, §13.2, §14 rules 4, 9, 10 and 14, §16.4, §18.2.
- `docs/plan/FEATURE_MAP.md`: the F6 row of section 1, sections 2.5 and 8.
- The draft, for behaviour and lessons only: `services/llm/` (provider clients, `cost_tracker`, `spend_guard`, `spend_policy`, `voice_metering`, `provider_breaker`, `live_capacity`, `premium_limits`, `abuse/`), `core/llm/`, `api/ai/ws_metering.py`, `api/admin/costs.py`, `api/admin/abuse.py`, `tasks/recompute_abuse.py`, `services/email/`, `tasks/send_email.py`, `entrypoints/scheduler_loops.py`; specifications 002, 008, 012, 016 and 028; `docs/SPEND_CONTROL.md`.

## Work

1. **Provider port.** The one place where AI provider clients are created (§18.2: OpenRouter, OpenAI Realtime, Google Gemini Live, pyannote, Mistral OCR). Operations: chat and streaming, embeddings, rerank, vision, image generation, speech recognition from a file and as a stream, realtime translation, voice sessions. Every call carries an effect key and writes exactly one `provider_costs` row with its result (monthly partitions, UUIDv7 keys); live capture is batched per minute (§8.1, inv-9).
2. **Deadlines, retries, breakers** exactly as §4.3: connect 10 s, stream stall 45 s, 120 s per analysis call, one retry before the first byte, a breaker per call kind, a 20% retry budget, and a provider-wide semaphore in Redis (§12).
3. **Spend control:** estimate, reserve, settle; the kill switch; ceilings that never stop a meeting or standard transcription (inv-13); expensive operations fail closed when Redis is unavailable (§13.2). Calls without a user (landing demo, help-centre assistant) are charged to a platform account with their own caps.
4. **Abuse guard:** consumption counters, scoring with hysteresis, routing to cheaper models, review queue and appeal, with the draft's behaviour (specifications 008 and 016). The admin API under `/v1/admin/costs` and `/v1/admin/abuse` keeps the paths the admin screens use; `GET /v1/admin/costs/guard` and `POST /v1/admin/costs/kill-switch` stay although no screen calls them, and `POST /v1/ai/abuse/appeal` is dropped (FEATURE_MAP.md, decision FM-5).
5. **Email:** a port that enqueues a templated message — transactional mail through the outbox on the `critical` queue, newsletters on `bulk`; the SMTP sender with the choice of sender mailbox per message type; the draft's base email layout. Slices own their templates and texts.
6. **Periodic-job registry:** a slice declares a job (name, interval, task); the scheduler process enqueues due jobs from `schedule_runs` in both homes; a missed interval runs once on start, not as a backlog (§12); scheduler loops are off outside the scheduler process (§14 rule 10).
7. **Telemetry:** per-provider metrics (latency, errors, session pool, cost per hour, §16.5) and the invariant monitor "provider calls without a cost row" (§16.4).
8. **Test doubles** of the provider port and the email port, so slices test without network access.
9. **Requirements from the [Leo architecture](../../design/leo/ARCHITECTURE.md)** (accepted on 2026-10-08):
   - the port serves **Jev decisions** (`decide`) through OpenRouter's Decisions API: pinned model `typesafe/jev-1.13`, a contract test on the response shape, one cost row per request priced by input tokens, deadlines set per call by the caller ([ADR 0026](../../adr/0026-leo-decision-layer-on-jev.md)); the Decision Layer itself (policies, thresholds, records) belongs to S09;
   - **breakers per (provider, model)**, not per provider, with a fallback model of the same tier from the registry (Leo architecture §11.1); this refines item 2;
   - spend reservation for a Leo turn and a separate daily budget for background runs, so initiative cannot exhaust a user's interactive quota (§5.4);
   - the **agent tool contract** in `core/agent_tools` (`ToolSpec`, `ToolContext`, `EffectClass`, `PlannedEffect`, `Preview`, `ToolResult`) and the field `FeatureParts.agent_tools`, framework-light like the kernel, so that slices can ship their tools before S09 ([ADR 0029](../../adr/0029-leo-tools-owned-by-domain-slices.md));
   - the periodic-job registry also lets a slice declare **due-row sources** walked by the scheduler, for `errands` and `proactive_triggers` (§12).

## Decisions to record as ADRs, confirmed by the user

- Where the provider port lives (in `core/` or as a feature with a `contracts` module) and its public interface.
- The price source for cost rows. The draft uses `services/llm/catalog_prices.py` and the model registry synced from OpenRouter; the registry itself belongs to S09.

## Definition of done

- A slice can call a model, send an email and declare a periodic job only through F6's contracts; an import-linter contract forbids provider SDK imports outside the port.
- A test proves that one call writes one cost row and that a replay with the same effect key writes no second row and no second debit (inv-9).
- A test proves that a job runs once per interval when two scheduler ticks race, in each home.
- Gates 100/100, mypy strict, tests and CI green.
