# F1 audit — keep, fix or rebuild the backend foundation

- **Date:** 2026-10-13. **Prompt:** [prompts/F1-audit.md](../prompts/F1-audit.md). **Subject:** `backend/` at `2dc30fb` (F1 steps 1–8 of 2026-10-02, renamed by ADR 0037).
- **Read:** CLAUDE.md; [ARCHITECTURE.md](../../design/ARCHITECTURE.md) and [Leo ARCHITECTURE.md](../../design/leo/ARCHITECTURE.md) in full; ADR 0001, 0005, 0008–0016, 0021–0025, 0029, 0034–0037; [F1 plan](../packages/F1-backend-foundation.md), [F6 plan](../packages/F6-platform-services.md), STATUS, REWRITE_PLAN, FEATURE_MAP (F1 and F6 rows); every file of `backend/src`, the tests named below, `compose.dev.yaml`, `docs/development.md`, `.github/workflows/ci.yml`, the D1 harness interface (`contracts/`).
- **Not read:** `frontend/` (its mandatory skills were not part of this audit; one fact about `/v1/health` comes from a search over the generated client). F1's files were not diffed against the draft line by line.
- **Size of what was audited:** 9 936 lines in `backend/src` (incl. 2 migrations), 13 145 lines in `backend/tests`, 779 tests.

## 1. Verdict

F1 is, in substance, what a from-scratch build to the target architecture would produce. It was designed from the architecture, not from the draft: the draft appears only as lessons turned into rules (F1 plan §1.2), and every part maps to a section of ARCHITECTURE.md. All gates pass. What a fresh build would do differently is narrow:

- **one draft-shaped mechanism** — the D1 gate is scoped by the draft's slice ownership, not by the native and external classes that alone must stay compatible;
- **two names kept for the draft's dashboards** — HTTP and loop metrics;
- **four gaps that Leo and the first slices hit at once** — outbox throughput, cross-home event consumers, monthly partitions, idempotency and pagination primitives;
- **a handful of small corrections.**

**Recommendation: keep F1 and fix it in place** (§6): five sessions, against nine to eleven for a rebuild that would most likely arrive at the same design.

## 2. Gate results

Run on 2026-10-13 from `backend/` against the local `compose.dev.yaml` services, test slot `shosai_test_1`:

| Gate | Result |
|---|---|
| `uv run ruff format --check .` | 277 files already formatted |
| `uv run ruff check .` | All checks passed |
| `uv run mypy .` (strict) | Success: no issues found in 276 source files |
| `uv run lint-imports` | 3 contracts kept, 0 broken (161 files, 758 dependencies) |
| `uv run pytest --cov` | 779 passed in 109.7 s; branch coverage 96% (the roles run as subprocesses are not counted, hence `composition/process.py` 55%) |
| `uv run python-doctor . --score` | 100 |
| `uv run pip-audit` | No known vulnerabilities |

The harness's end-of-run check passed, so the test databases were left clean.

## 3. Findings

Classes: **keep** · **fix** (change and size) · **remove**. Sizes: XS < 1 h, S ≈ half a session, M ≈ one session.

### 3.1 Architecture (prompt item 1)

| ID | Finding | Evidence | Class |
|---|---|---|---|
| A1 | Two homes, home-aware access: one engine per home per process with role pool sizes, `max_overflow=0`, 2 s pool wait; transactions open in the scope's home with one scope statement; a home out of reach gives 503 `home_unavailable` for that home only; swapped addresses or a schema behind the code stop the start. Matches §4.1 rules 3–4, §4.3, §13.2, §14 rules 1–2 | `core/db/engines.py:51-60`, `core/db/transactions.py:77-87`, `core/db/home_checks.py:111-153`; ADR 0010, 0013 | keep |
| A2 | Tenancy scope and RLS groundwork: `SET LOCAL` values per transaction, `app_user_id()`/`app_org_id()`, `enable_company_isolation`. The standard policy shows rows with `org_id IS NULL` to every scope, so RLS isolates companies only; `app_user_id()` has no policy yet. This is what §7 asks for (RLS as the second line for companies), but personal rows have no second line | `core/db/migration_scope.py:24`, migration `e6f66cdc6ea6`; §7, nfr-15 | keep; decision OD-5 for S02 |
| A3 | One bucket: one client, explicit timeouts, 3 attempts, no DB session across calls, presigned uploads bound to type and length, keys never logged. Matches ADR 0014, §14 rule 8, inv-11 | `core/storage/s3_client.py:52-64`, `core/storage/port.py` | keep |
| A4 | Valkey: one client per process, no client retries, per-call deadlines, TLS required in production. The task scripts touch several keys in one script (stream + dead letter; all queues in the gauge script) without hash tags; on a cluster-mode Valkey they fail with `CROSSSLOT`. §4.2 describes a managed Valkey "with replica", which reads as non-cluster | `core/kv/connection.py`, `core/tasks/scripts.py:56-80`, `core/config/gate.py:91-97` | keep; fix only if OD-6 says cluster (S: hash tags `{tasks:<queue>}`) |
| A5 | Tasks and broker: stream per queue with only unfinished tasks, enqueue ≤ 50 ms or 503, lease 120 s renewed every 15 s, retries as delayed redeliveries, 5 deliveries then dead letter with secrets masked, unknown task dead-lettered and counted, tick markers. Matches §4.3 "Valkey → Workers", §12, §14 rule 9, §16.4 | `core/tasks/*`; ADR 0016 | keep |
| A6 | **Outbox throughput is capped at 100 events per 5 s per home.** Each scheduler tick runs exactly one relay pass of at most 100 rows; the next pass waits for the next tick even when rows are due. §12 sets "relay limit at batch 100 per 5 s" and a revisit at sustained > 20 events/s. The Leo architecture expects ≈ 25 signals/s at peak at 10 000 DAU, most of them outbox events (`mail.received`, meeting and calendar events), and ≈ 250/s at 100 000 DAU, and requires the design to hold that column "without a structural change". The two documents conflict; with the RU home at 80% of the load, a peak backs up the relay and pages the "outbox events older than 5 min" monitor | `core/events/relay.py:103-119`, `core/events/relay_limits.py:15`, `core/events/system.py:20`; ARCHITECTURE §12 (revisit table), Leo §2.4, §12 | **fix** S: a pass keeps claiming while it took a full batch, within its deadline, with a metric of passes and rows per tick; the documents' conflict goes to the owner (OD-4) |
| A7 | **No cross-home consumer.** A delivery always opens its transaction, and writes its delivery mark, in the home of the event. A consumer whose effect lives in the EU home — ADR 0005's promo-code use applied "through the outbox" from a purchase in the RU home, any update of platform or directory tables — cannot apply its effect and its mark atomically | `core/events/delivery.py:113`; ADR 0005 (consequences, promo codes); §6 | **fix** S–M: `EventSubscription.home` (default: the event's home; or a fixed home such as `Home.EU`); the delivery opens the mark and the effect there; a test with an RU event and an EU consumer |
| A8 | **No monthly partitions.** §8.2 lists twelve high-volume tables with UUIDv7 keys and monthly partitions, retention by dropping partitions; four of them are Leo's (`agent_messages`, `agent_runs`, `agent_decisions`, `agent_audit`). Core has neither a migration helper for a partitioned parent nor the job that creates partitions ahead and drops expired ones; F6 plans that job for `provider_costs` only | no `partition` in `backend/src`; ARCHITECTURE §8.2; F6 plan §3.4 | **fix** M: `core/db` helper (parent, ahead creation, drop by retention) declared per table; upkeep as a scheduler tick now, moved to `schedule_runs` with F6 step 1 |
| A9 | **No idempotency primitive.** §10 requires an `Idempotency-Key` per Leo user message, a single upload id, a one-time invite token returning the same membership; inv-9 requires one cost row per effect key; Leo item keys `action_id:index` must be stored in the effect's transaction. Only `processed_events` exists, for events. Each slice would hand-roll the same table | `core/events/records.py:77-87`; ARCHITECTURE §10, inv-9; Leo §8.4 rule 2; F6-C1 | **fix** M: a core effect-key ledger written in the caller's transaction (`key` PK, `scope`, `recorded_at`, a reference to the stored result), an HTTP dependency for `Idempotency-Key`, retention by job; F6-C1's `provider_cost_effects` becomes one use of it |
| A10 | **No pagination contract.** §10: "Collections use cursor pagination with a maximum page size." Every slice and Leo (threads, messages, actions, memory) needs the same opaque cursor and page shape | ARCHITECTURE §10 contract rules | **fix** S: core value types (opaque cursor over a sort key, page-size bound, `items` + `next_cursor`) and a FastAPI dependency |
| A11 | **The production gate does not run in staging.** `enforce_production_gate` returns unless `ENVIRONMENT=production`; staging at `one.whisperer.one` is reachable from the internet and holds real-shaped data, yet may start without TLS to the homes, without `rediss://`, with API docs on and without trusted proxies | `core/config/gate.py:49-50`; §15 | **fix** S: the gate applies to `staging` too (the owner may exempt API docs there) |
| A12 | Process roles, ops port, readiness that reports dependencies but does not fail on them, ordered drain within 30 s, loops only in the scheduler. Matches §5, §13.2, §14 rule 10 | `composition/*`, `core/runtime/*`, `core/health/*` | keep |
| A13 | Observability: JSON lines through a bounded queue, redaction, span privacy sampler, bounded span export with drop counter, trace context across HTTP, tasks and outbox events, request id on every response. Matches §16.1–§16.2, §16.8 | `core/observability/*`, `core/tasks/tracing.py`, `core/events/publishing.py` | keep |
| A14 | Errors: one envelope on every path, `X-Request-ID` on the last-resort 500, 422 without input. Matches §10 and ADR 0008 | `core/web/boundary.py`, `core/web/error_handlers.py` | keep |

### 3.2 Leo (prompt item 2)

| ID | What Leo needs from the foundation | F1 today | Class |
|---|---|---|---|
| L1 | Tool contract `core/agent_tools`, `FeatureParts.agent_tools`, provider port with `decide`, spend reservation and the background budget per user, due-row sources for errands and proactive triggers | Absent and planned in F6 (§3.10, §3.6, §3.9). `CoreServices` and `FeatureParts` are frozen dataclasses with defaulted fields, so F6 adds fields without changing any slice | left cleanly to F6 — keep |
| L2 | Thread lease, run checkpoints and event logs, one-time secret vault, user state in Valkey; two home transactions per turn; GCRA admission; outbox events with ids only; trace context into background runs | Valkey client and `DistributedLocks.hold/extend` in `CoreServices`; `HomeTransactions`; `RateLimiter`; `DomainEvent` field rule; task and outbox tracing | provided — keep |
| L3 | Partitioned `agent_messages`, `agent_runs`, `agent_decisions`, `agent_audit`; `Idempotency-Key` on turns and item keys on actions; cursor pages for threads, messages, actions, memory; proactive signals at 25/s peak through the outbox | Missing: A8, A9, A10; capped: A6 | covered by fixes A6, A8–A10 |
| L4 | SSE runs up to 180 s on the API role | The request boundary records a request when the response ends, so a 180 s stream lands in `http_request_duration_*` and skews the cabinet latency SLO (§16.3) | **fix** S, with S09's first SSE route: streaming responses get their own outcome (time to first byte, or a separate metric), not the request histogram |
| L5 | `agent.domain`, `decisions.domain`, `memory.domain` import neither LangGraph nor provider SDKs (Leo §3.3) | Not yet expressible: no slices; see E3 | covered by E3 |

Nothing in F1 blocks the Leo architecture. Its first phases (Leo §15, phases 2–3) depend on F6 and on the four fixes above.

### 3.3 Draft carry-over (prompt item 3)

| ID | Finding | Evidence | Class |
|---|---|---|---|
| D1 | **The D1 gate is scoped by the draft's slice ownership.** `FeatureModule.contract_slice` must be an id of the old cut (`S04`, `F6`); composition turns the listed slices into the harness scope; the test checks every draft route those slices owned in D4's map. Under the new goal only native routes and external callbacks must survive; the ownership field comes from FEATURE_MAP, which SLICE-MAP replaces. In the current harness a missing `web` route is a warning and does not fail, so the gate is noisy rather than wrong today, but it ties every slice's identity to the old cut | `core/features.py:44-46, 108, 118-120`; `composition/features.py:36-38`; `tests/composition/test_public_routes.py:70-81`; `contracts/src/shosai_contracts/inputs.py:73-83` | **fix** S: drop `contract_slice`; the gate checks every `native` and `external` route the composed apps serve, for any slice; a coverage list names the native and external routes not served yet (informational now, a gate before M2); the harness `Scope` gains a class filter (contracts/) |
| D2 | `GET /v1/health` exists "for D1"; D1 classes it `web`, owned by F1. The new cabinet's generated client still calls it, so the route stays, for the cabinet's reason | `core/web/health.py:1`; `contracts/draft/consumers.json:6364-6366`; `frontend/src/lib/api/client.test.ts` | keep (docstring XS) |
| D3 | **Metric names kept for the draft's dashboards.** The five HTTP metrics keep prometheus-fastapi-instrumentator's names, help texts, labels and buckets because "the owner required the existing contract"; loop metric names are "the draft's" so its alert rules carry over. v2 has no dashboards or alerts yet (F5 is `todo`). The mechanism of ADR 0012 — template from FastAPI's routing, no second match, closed label sets, 7 µs per request — is right and stays | ADR 0012 decision 2 and "Alternatives"; F1-C27; `core/web/http_metrics.py`; `core/runtime/loops.py:53-71` | **fix** S if OD-3 accepts: OpenTelemetry HTTP semantic-convention names and labels (`http_server_request_duration_seconds{http_route,http_request_method,http_response_status_code}`) on the same boundary; ADR 0012 amended, §16.1 updated |
| D4 | Error envelope `detail` (ADR 0008): native clients read `detail` with a per-route shape; the default `detail = code` on new routes is harmless | ADR 0008; contracts README "Error bodies" | keep |
| D5 | Fernet key ring with the draft's variable names: needed so that M1's migrated ciphertexts decrypt; no user in `src` until S12 | `core/crypto/key_ring.py`; DATA_MAPPING S-3 | keep |
| D6 | `Locale.hreflang` and `Locale.og_locale` are SEO metadata of the public site, which is `site/` on Next.js (ADR 0021); nothing in the backend uses them | `core/i18n/locales.py:13-41` | **remove** XS |
| D7 | The draft's lessons (F1 plan §1.2) each answer an incident or a rule of the architecture; queue concurrency (16/5/3/3) is the draft's production setting | `core/tasks/queues.py:40-49` | keep; re-size by Little's law when the first slice's tasks exist |
| D8 | Leftovers of the rename: the migration lock key is "WhisperM" in ASCII; the `Home` docstring gives each home its own S3 bucket, against ADR 0014 | `core/db/migrations.py:29-30`; `core/kernel/homes.py:7` | **fix** XS |

### 3.4 Engineering rules (prompt item 4)

| ID | Finding | Evidence | Class |
|---|---|---|---|
| E1 | Gates: all green (§2) | — | keep |
| E2 | Versions: Python 3.14.7, FastAPI 0.142.2, Pydantic 2.13.5, SQLAlchemy 2.1.2, Alembic 1.20.0, psycopg 3.3.6, redis-py 8.1.0, TaskIQ 0.13.0, uvicorn 0.54.0, uvloop 0.23.0, aiobotocore 3.9.2, structlog 26.1.0, OpenTelemetry 1.45.0 — the stack table and §18.2, pinned in `uv.lock` | `backend/pyproject.toml`, F1 plan §1.3 | keep |
| E3 | **import-linter covers layers, slice independence and the pure kernel, not the inside of a slice.** CLAUDE.md requires that domain logic not depend on the framework, the database or transport; Leo §3.3 adds a rule for three domains. With wildcards this is expressible now, so every slice is born under it | `backend/pyproject.toml` `[tool.importlinter]` (3 contracts) | **fix** S: `forbidden` contract `shosai.features.*.domain` → fastapi, starlette, sqlalchemy, redis, taskiq, httpx, aiobotocore, langgraph, provider SDKs; fixture test like the existing one |
| E4 | Async I/O throughout; no `print`; broad `except Exception` only at process and loop boundaries, each logged with its stack; comments and log messages in Russian, docstrings in English (checked by a test); largest file 263 lines (`core/tasks/broker.py`) | `tests/architecture/test_docstrings_english.py`; `scripts/ci/check_repository.py` | keep |
| E5 | Configuration only from the environment through pydantic-settings, explicit mapping, no dotenv; every variable documented, a test keeps `.env.example` equal to the settings | `core/config/*`, `tests/core/config/test_env_example.py` | keep |
| E6 | Feature-first layout: `core` / `features` / `composition` / `entrypoints` as §5 fixes; `core` is horizontal by the architecture's own design | ARCHITECTURE §5 | keep |
| E7 | Compose and CI follow the Docker skills: pinned tags, health checks with `service_healthy`, loopback-only ports, read-only root, `no-new-privileges`, memory limits, log rotation; the backend job runs on the same services. There is no backend Dockerfile — F4's scope | `compose.dev.yaml`, `.github/workflows/ci.yml` (job `backend`) | keep |

### 3.5 Quality of what is there (prompt item 5)

| ID | Finding | Class |
|---|---|---|
| Q1 | No significant overengineering. The largest own component, the task broker (≈ 1 300 lines of `core/tasks` plus tests), is justified by ADR 0016, whose reasons still hold (§4). | keep |
| Q2 | No dead code beyond foundation parts waiting for their first slice, each tested and with a named user: key ring (S12), Accept-Language (F6 email, S01), locks, the rate-limit dependency (S01 sign-in), multipart uploads (S08). | keep |
| Q3 | Tests: 779, property tests where input space matters (limiter, labels, redaction, events); the roles are tested as real subprocesses against F3; the harness (2 261 lines) is what ADR 0009 and CLAUDE.md "Clean up after every run" demand. No test was found that asserts nothing. | keep |
| Q4 | Missing parts a fresh build would have: A8, A9, A10, E3; and the kernel's id and clock helpers that F1 plan §3.1 announces — three ad-hoc `uuid.uuid7()` calls instead (`core/web/request_ids.py:28`, `core/events/outbox.py:72`, `core/tasks/broker.py:53`). | fix XS (`core/kernel/ids.py`) with A9 |

### 3.6 F6 plan (prompt item 6)

Parts that rest on the draft's behaviour and must be re-derived from the product:

| ID | Part of the F6 plan | Why it rests on the draft | What to do |
|---|---|---|---|
| F6-1 | §1.1 row "D1" and step 10: `/v1/admin/costs/{guard,kill-switch,summary,timeline}`, `/v1/admin/abuse`, `/{user_id}`, `/{user_id}/action` with the draft's paths; DoD "The D1 gate passes for the F6 routes"; the F6 prompt keeps `guard` and `kill-switch` "although no screen calls them" | D1 classes them `web` (summary, timeline, abuse ×3) and `unused` (guard, kill-switch): nothing outside the draft depends on them | Design the admin API from the new cabinet's admin screens and the operator's needs; drop the D1 DoD |
| F6-2 | §3.7, F6-C8, F6-C9, step 7: the abuse guard with the draft's features, weights, sigmoid scoring, states and thresholds (0.5 / 0.75 / 0.4, two confirm windows), shadow mode by default (spec 008), recompute every 300 s, input caps 32 K tokens and 6 images ≤ 8 MB | Calibrated on the draft's traffic and pricing; spec 008 is a draft specification | Decide what abuse must be stopped at launch; hard spend ceilings and the concurrency cap (§3.6) may be enough until v2 has its own data (OD-8) |
| F6-3 | §3.8: "the base layout is the draft's `layout.html`" | Visual design is the new design system's (ADR 0022) | Email layout from the new design; keep the technical rules (tables, inline styles, RTL) |
| F6-4 | §3.6: platform accounts `landing_demo`, `help_assistant` | Rest on FM-1, the keep decision for two draft modules | Re-derive from SLICE-MAP |
| F6-5 | §1.1 row "D3": `abuse_states`, `abuse_events`, `voice_sessions`, `translation_session` carried; spend counters re-seeded; `spend:global:kill` carried | Draft data and keys | Decide in M1's terms what history v2 needs; the abuse history and the draft's Valkey keys probably not |
| F6-6 | Provider port, cost rows with effect keys, price table and seeds, exchange rate, deadlines, breakers per model, semaphore, retry budget, call classes, `schedule_runs`, email outbox, agent tool contract | Derived from §4.3, §8.1, §12, §13.2, inv-9, inv-13 and the Leo architecture; the draft only supplies lessons and seed data | keep; verify the seeded prices against the providers' lists when seeding |
| F6-7 | F6-C1 `provider_cost_effects`; partition upkeep of `provider_costs` | Both are instances of the missing core primitives | Build on A9 and A8 instead of F6-local tables and jobs |

## 4. Do the reasons of ADR 0008–0016 still hold?

| ADR | Decision | Reason holds? |
|---|---|---|
| 0008 | One error envelope with a compatible `detail` | Yes: the `detail` shapes are read by shipped native clients |
| 0009 | Test slots by advisory lock, `TEST_*` only | Yes |
| 0010 | Home-scoped revisions in one history; start check | Yes |
| 0011 | GCRA limiter in Valkey | Yes: slowapi is still synchronous |
| 0012 | HTTP metrics in the request boundary | The mechanism: yes (CPU, closed labels, private-API coupling). The pinned instrumentator names: no — they served the draft's dashboards (D3) |
| 0013 | psycopg 3 behind PgBouncer | Yes: four round trips per scoped read to the RU home instead of six |
| 0014 | One bucket in Russia | Yes: an infrastructure fact set by the owner |
| 0015 | aiobotocore instead of aioboto3 | Yes as of the decision; re-check if a slice needs managed transfers |
| 0016 | Own broker on TaskIQ's interface | Yes: taskiq-redis's gaps are structural (own pool, no deadline, no delivery limit, trimming unfinished tasks) |

## 5. Estimate of the two options

| | Fix F1 in place | Rebuild from an empty `backend/` |
|---|---|---|
| Sessions | 5 (§7), each S–M | 9–11: F1 took one planning session and nine implementation sessions on 2026-10-01/02, with 13 owner decisions; a rebuild repeats them and must still contain the five fixes |
| Code | ≈ 1 500–2 500 lines changed, tests included | ≈ 10 000 lines of `src` and 13 000 lines of tests written again |
| Repeats | nothing | the harness, the CI job, every measurement behind ADR 0012, 0013 and 0016, every edge case the tests found (TaskIQ's acknowledgement order, the managed Valkey's 5 s cut of blocking reads, `power()` overflow in the relay, Alembic's step names) |
| Risk | Low: v2 is not deployed, so renaming metrics or event fields needs no migration; every change is covered by the existing 779 tests | Regressions in exactly those edge cases; F6 and every slice wait two weeks of sessions; the likely result is the same design, since each part follows the architecture rather than the draft |
| Gain | The draft-shaped parts go (D1, D3, D6, D8); the gaps that Leo and the first slices would meet are closed before any slice exists (A6–A11, E3, L4) | A codebase without F1's history; no structural gain was found that the fixes do not also give |

## 6. Recommendation and decisions for the owner

**Keep F1 and fix it in place.** F1 already is what the from-scratch goal asks for; rebuilding it would spend the most sessions on the parts that are right.

| # | Decision | Proposed answer | Trade-off |
|---|---|---|---|
| OD-1 | Keep and fix F1, or rebuild | Keep and fix (§5) | Rebuild costs 4–6 more sessions and delays F6 and the slices for no structural gain found |
| OD-2 | Scope of the D1 gate | By class: every `native` and `external` route the composed apps serve, any slice; a coverage list of the ones not served yet, required empty before M2; `contract_slice` removed | The gate no longer warns about dropped `web` routes — by the new goal that is no longer a signal |
| OD-3 | Names of the HTTP and loop metrics | OpenTelemetry semantic conventions on the existing boundary (ADR 0012 amended) | Off-the-shelf Grafana dashboards and FastAPI's native metrics speak these names; the draft's dashboards do not carry over, and none exist in v2 |
| OD-4 | Outbox throughput versus Leo's signal volume | Relay drains while its batch is full (A6) now; keep §12's revisit trigger and amend Leo §12 to say which signals pass the outbox and that a sustained > 20/s per home triggers the revisit | Drain mode lifts the per-tick cap without a new store; a stream platform (the §12 revisit) is decided on measurements, not now |
| OD-5 | RLS for personal rows (`org_id IS NULL`) | Decide in S02's plan; F1 changes nothing now | A user-isolation policy adds a second line for personal data, at the cost of the sweeps' dedicated role (F1-C6) |
| OD-6 | Topology of the managed Valkey | Non-cluster with replica, as §4.2 reads; if cluster, hash tags in the task keys | A cluster would need every multi-key script reworked |
| OD-7 | Production gate in staging | Same gate as production; API docs may stay on in staging | Staging needs real TLS certificates for the homes and Valkey from its first day |
| OD-8 | F6 parts that rest on the draft (§3.6) | Re-plan F6-1 … F6-5 in one session after SLICE-MAP is approved; F6 steps 1–6 and 8–9 keep their content | Abuse scoring may arrive later than the draft had it |

## 7. Next steps for the recommended option

One session each; every step ends with the gates of §2 green and is committed after «Принято». Steps 1–5 need no owner resources and may precede F6.

| Step | Content | Skills | Done when |
|---|---|---|---|
| 1 | **D1 gate by class and small corrections.** OD-2 (harness `Scope` with a class filter in `contracts/`, `contract_slice` removed from `FeatureModule`, composition and README, coverage report); E3 (domain contract with a fixture test); D6, D8, D2 docstring; kernel id helper (Q4) | fastapi, python-doctor | A fixture slice that breaks a native route fails the gate whatever its name; a fixture domain importing SQLAlchemy fails `lint-imports`; `contract_slice` appears nowhere |
| 2 | **Metric names and the staging gate.** OD-3 in `core/web/http_metrics.py` and `core/runtime/loops.py`, ADR 0012 amendment, §16.1 and §18.2; OD-7 in `core/config/gate.py` and its tests | fastapi, python-doctor, observability | The contract test pins the new names and labels; a staging process with an unsafe setting refuses to start and names it |
| 3 | **Events: drain and cross-home consumers.** A6 (passes while the batch is full, within the deadline; metrics) and A7 (`EventSubscription.home`, mark and effect in the consumer's home); §12 note per OD-4 | fastapi, python-doctor, messaging-streaming, consistency-coordination, Docker ×4 | 1 000 due rows in one home are relayed within one tick's deadline; an RU event applies its effect in the EU home exactly once under redelivery |
| 4 | **Idempotency and pagination primitives.** A9 (effect-key ledger, `Idempotency-Key` dependency, retention) and A10 (cursor, page bound, page shape); revision for both homes | fastapi, python-doctor, api-design, data-storage, Docker ×4 | A replayed key returns the stored outcome and writes nothing; a cursor survives inserts between pages; page size above the bound is 422 |
| 5 | **Monthly partitions.** A8: migration helpers for a partitioned parent, ahead creation and drop by retention, upkeep tick per home in the scheduler; a fixture table proves both | fastapi, python-doctor, data-storage, task-scheduling, Docker ×4 | Partitions for the next two months exist after a tick; an expired partition is dropped; downgrade restores the catalog fingerprint |
| 6 | **F6 re-plan** (after SLICE-MAP is approved): rewrite F6-1 … F6-5 and F6-7 in the F6 plan per OD-8 | fastapi, task-scheduling, resilience-failure | The owner approves the amended F6 plan |

L4 (streaming responses in the request boundary) is done with S09's first SSE route.

## 8. Owner's decisions (2026-10-13)

| # | Decision |
|---|---|
| OD-1 | **Keep F1 and fix it in place** (§7 steps 1–5). |
| OD-2 | The D1 gate checks the **native routes of the shipped macOS and Windows clients** only, for any slice; `contract_slice` is removed. External callbacks are not gated: each slice designs its own and re-registers the URL with the provider. |
| OD-3 | OpenTelemetry semantic-convention names for HTTP and loop metrics; ADR 0012 amended. |
| OD-4 | Relay drains while its batch is full; §12's revisit trigger stays; Leo §12 amended as proposed. |
| OD-5 | RLS for personal rows is decided in the `workspaces` plan. |
| OD-6 | **Valkey runs in the EU only, on its own machine, reached from the production server over a private network; the EU home's PostgreSQL is reached over the private network too.** Not a cluster, so A4 needs no hash tags. TLS stays required on these links (OD-7). Valkey is managed by Timeweb Cloud in the EU **with a replica**, as ARCHITECTURE §4.2 assumes. |
| OD-7 | **Staging runs under the full production gate**, API docs included: the gate applies to every environment except `local` and `test`. |
| OD-8 | Re-plan F6-1 … F6-5 and F6-7 after SLICE-MAP is approved; the other F6 steps keep their content. |

The foundation work runs as §7 steps 1–5, one session each, before F6.
