# ADR 0034 — Platform services live in `core`: provider port, email, periodic jobs, agent tool contract

- **Status:** accepted by the owner on 2026-10-08 (F6 planning, decision F6-D1).
- **Package:** F6, platform services; used by every slice that calls a model, sends an email, declares a periodic job or exposes a tool to Leo.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §5, §12, §14 rules 4 and 10, §19 ("Provider port writes every cost row"); [Leo architecture](../design/leo/ARCHITECTURE.md) §3.3, §4, §13.1; [ADR 0029](0029-leo-tools-owned-by-domain-slices.md); [FEATURE_MAP.md](../plan/FEATURE_MAP.md) decision FM-4; [F6 plan](../plan/packages/F6-platform-services.md).

## Context

FM-4 created F6 because most slices need the same services from their first step: a model call that writes its cost row, an email, a periodic job. The draft imported its provider layer from 10 slices and its email from 7, and created provider clients in about 30 places, several of them never closed (draft `services/llm/router.py` callers, `features/*/infrastructure`).

Where these services live decides how a slice reaches them. F1 gives a slice one thing at build time: `CoreServices`, the process's clients and ports, passed by injection (`core/features.py`). A slice may import another slice only through its `contracts` module, and core may not import a feature (`layers` contract). Two placements were weighed:

| Option | What a slice does | Cost |
|---|---|---|
| Packages in `core`, instances in `CoreServices` | receives `services.ai`, `services.email`; declares jobs and tools in `FeatureParts` | core grows by business-adjacent code (cost rows, spend rules, abuse scoring) |
| A feature `features/ai` with a `contracts` module | imports the contract types, receives an implementation from composition | a second injection path — a slice's `build` would need ports of other slices, which F1 does not have — for the same behaviour |

The Leo architecture already places the provider port in core (§4, "Provider port | F6 (core)") and puts the tool contract in `core/agent_tools` (ADR 0029).

## Decision

1. **Packages in core**, each with a public surface and adapters behind it:
   - `core/ai` — the provider port: every model, speech, vision, image, OCR, diarization and decision call; cost rows with effect keys; prices; spend control; breakers and the provider semaphore; the abuse guard's counters, scoring and routing state;
   - `core/email` — the email port, message rows, the SMTP sender and the base layout;
   - `core/schedule` — the periodic-job registry, `schedule_runs` and due-row sources;
   - `core/agent_tools` — the framework-light tool contract of ADR 0029;
   - `core/exchange_rates` — the USD/RUB rate ([ADR 0036](0036-exchange-rate-owned-by-platform-services.md)).
2. **One instance per process.** Composition builds the provider port and the email port once and passes them in `CoreServices` (`ai`, `email`, `exchange_rates`). Slices declare periodic jobs, due-row sources and agent tools in `FeatureParts` (`periodic_jobs`, `due_sources`, `agent_tools`); composition hands them to the scheduler and to the agent.
3. **No provider client outside `core.ai`.** An import-linter contract forbids the provider SDKs (`google.genai`, `websockets` as a provider transport, `openai`, `deepgram`, `mistralai`) outside `shosai.core.ai`; a test fails when a provider host name appears in source outside `core/ai`, which covers raw HTTPX calls the import contract cannot see.
4. **Framework-light contracts.** `core/agent_tools` and the value types of `core/ai` (requests, results, call context, effect keys) import no FastAPI, SQLAlchemy, redis, HTTPX or provider SDK — enforced by an import-linter contract like the pure kernel.
5. **Business rules that are not platform rules stay in slices.** Tariffs, premium budgets and credit ledgers (S03), the model registry, roles and defaults (S09), templates and texts of emails (each slice), the Decision Layer's policies (S09) live in their slices. The port receives them as call parameters (a model route, a spend limit) or through a hook a slice registers (cost settlement, F6 plan §3.4).
6. **The admin HTTP API** under `/v1/admin/costs` and `/v1/admin/abuse` is a thin slice `features/ai_control` (contract slice F6) over core's report and review services. It needs the administrator principal from S01, so it is the last step of F6, built once S01 is done (F6-D3). *Amended on 2026-10-13 by [ADR 0041](0041-platform-services-replanned-from-the-product.md): F6 has no admin HTTP route; `studio` and `identity` serve its services from their own admin routers, and `features/ai_control` is not built.*

## Consequences

- A slice calls a model, sends an email and declares a job from its first step, with no dependency on another slice.
- Core grows by an estimated 5 000–6 000 lines across five packages, every file within the 300-line limit, each package with its own README section and tests.
- Composition gains three fields in `CoreServices` and three in `FeatureParts`; the route snapshot and the D1 gate cover the admin routes when step 10 adds them.
- Tables owned by core (`provider_costs`, `provider_cost_effects`, `abuse_states`, `abuse_events`, `email_messages`, `schedule_runs` in both homes; `provider_prices`, `exchange_rates` in the EU home) join the migration history like `outbox_messages`.

## Revisit when

- A platform service gains a consumer outside the application process, or needs its own deployment.
- A slice needs to replace a platform rule (for example its own spend ceiling) rather than pass a parameter: the rule moves into that slice behind a contract.
