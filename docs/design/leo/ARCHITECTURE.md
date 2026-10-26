# Leo — agent architecture

- **Status:** accepted by the owner on 2026-10-08, with ADR 0023–0033. The amendments of [§16](#16-proposed-amendments-to-the-target-architecture) are applied to the [target architecture](../ARCHITECTURE.md). Amended on 2026-10-13 by the [slice map](../../plan/SLICE_MAP.md): the `models` slice is absorbed by `studio` ([ADR 0038](../../adr/0038-feature-slices-derived-from-the-product.md)); Leo is one per person across Personal and every workspace ([ADR 0039](../../adr/0039-one-account-per-person-with-workspaces.md)); package ids S01–S17 are replaced by slice names. Amended on 2026-10-23 by the [`agent` slice plan](../../plan/slices/agent.md) ([ADR 0068](../../adr/0068-leo-agent-slice.md)): sources from tools (§13.2), LangGraph's boundary (§3.3), rules before Jev (§6.3), parts built with their first consumer (§8.2, §8.4, §13.2), feedback and donated evaluation cases (§11.4), the cabinet's renderer (§17 Q-2), and turns run by worker processes of a dedicated `agent` queue, the API only streaming them (§3.1, §11.1, §12). Amended on 2026-10-26 by agent step 11c (agent-derived): donated cases are replayed on the host by `shosai agent eval cases replay`, every read audited (§11.4).
- **Scope:** Leo, the proactive AI agent at the centre of the workspace (brand Shosai). The slices `agent`, `decisions`, `memory`, `proactive` and `errands`, and the agent-facing parts of `capture` (voice), `mcp`, `connectors` and `studio` (models and prompts).
- **Inputs:** [AUDIT.md](AUDIT.md) (the draft's Leo); target architecture §1–§22; the new cabinet design in `frontend/src/features/leo`; the D1 contract (`contracts/draft/`); [Jev](#6-decision-layer-and-jev) public documentation as of 2026-10-08.
- **Diagram:** [architecture.html](architecture.html) — components and layers, the turn and approval path, the proactive pipeline.
- **Decisions:** [ADR 0023](../../adr/0023-leo-agent-core-layers.md) – [ADR 0032](../../adr/0032-leo-stream-protocol-v2.md), index in [§14](#14-architecture-decision-records).

**Reading guide.** §2 states what Leo must achieve. §3–§4 give the shape. §5–§9 are the five subsystems: lifecycle, decisions, memory and context, tools and skills, proactivity. §10–§13 cover state, the quality attributes and integration. §15 is the plan. §16–§17 list what the owner must decide.

---

## 1. Audit summary

The full audit with evidence is in [AUDIT.md](AUDIT.md). Six findings shape this design:

1. **Confirmation is not a guarantee** (A1–A3). A write can run twice after a crash. A voice "yes" is the model's own tool call. MCP writes skip confirmation entirely. inv-12 does not hold.
2. **The conversation has no server home** (C1, C2). History lives in the browser. The server thread dies after 24 h. Concurrent turns overwrite each other.
3. **Context is unbudgeted** (T1, T2). About 20–25 K tokens of tool schemas go out every round. History is capped by message count, not tokens. Large tool results are re-sent on every round.
4. **Untrusted text is trusted** (A4–A7). Mail summaries are written as assistant turns. Memory is injected as "your own knowledge". The wrapper can be escaped, and unconfirmed egress tools complete an exfiltration chain.
5. **Initiative is static rules over global scans** (P1–P3). Urgency is fixed per kind, with no value, no attention state and no feedback. Every 5 minutes the system polls over all users.
6. **Boundaries are crossed everywhere** (C3, C4, C10). Tools reach into the ORM models of 16 domains. The principal is built five ways. Calls bypass spend control.

The redesign keeps the behaviours listed in [AUDIT.md §3](AUDIT.md#3-what-the-redesign-keeps) and drops the approaches listed in [§4](AUDIT.md#4-what-the-redesign-drops).

---

## 2. Goals, requirements, design point

### 2.1 What Leo is for

Leo is the single agent of the workspace. It answers, acts with the user's confirmation, and **takes initiative when the moment and the value justify it**. It is one capability set shared by every feature, so it reads as part of the workspace, not as a chat bolted on.

### 2.2 Functional requirements

| id | Requirement | Source |
|---|---|---|
| L-1 | Conversational turns in text and voice, in one thread per scope, persistent and continuous across devices | fr-4, fr-9, C1 |
| L-2 | Tools over every domain the user can access, under the same access policy as the UI | fr-4, fr-13, inv-14 |
| L-3 | A write runs at most once and only after the user's confirmation, on any channel (web, voice, native, MCP, errand) | inv-12 |
| L-4 | Proactive suggestions grounded in workspace events, delivered at a good moment, rated by the user, budgeted | slice `proactive`, P1–P5 |
| L-5 | Long-term memory the user can see, correct and switch off; provenance for every fact | slice `memory`, M1–M4 |
| L-6 | Skills: platform playbooks and user-installed SKILL.md packages that shape behaviour without granting rights | slice `agent`, M6 |
| L-7 | Delayed actions (errands) re-validated at run time | slice `errands`, P4 |
| L-8 | Exposure of Leo's tools to external MCP clients under the same confirmation rule | slice `mcp`, A3 |
| L-9 | Answers in the user's chosen language; every model-facing text in English | CLAUDE.md, §14 rule 14 |

**Out of scope here:** model training and fine-tuning, multi-company collaboration (target architecture §21), autonomous writes without confirmation (§9.2 Q-4).

### 2.3 Non-functional targets

| id | Axis | Target |
|---|---|---|
| L-N1 | Platform overhead per turn | ≤ 500 ms p95 for EU users (nfr-7, §16.3); tracked but not paged for Russian users (§20) |
| L-N2 | Time to first visible event | `run.started` ≤ 150 ms after the request reaches the API (EU) |
| L-N3 | Input tokens of a first model round, default tier | ≤ 12 K p50, ≤ 20 K p95 (draft: ≈ 30 K before history) |
| L-N4 | Run failures | < 1% of runs end `failed` for platform reasons, not counting provider outages |
| L-N5 | Confirmation integrity | 0 actions executed twice, 0 actions executed without an approval (invariant monitors) |
| L-N6 | Proactive quality | precision (acted on or rated useful ÷ delivered) ≥ 30% after calibration; dismissal ≤ 40%. These are initial hypotheses, revised after 4 weeks of data |
| L-N7 | Isolation | no tool result, memory or suggestion carries data the user may not see (nfr-15) |
| L-N8 | Degradation | Jev, Qdrant or one model down → Leo keeps answering; Valkey down → new turns refused (§13.2) |

### 2.4 Design point

These are assumptions, derived from the target architecture's 10 000 DAU. They are checked against the design at 100 000 DAU.

| Quantity | 10 K DAU | 100 K DAU | Derivation |
|---|---|---|---|
| Leo users per day | 4 000 | 40 000 | 40% of DAU (assumption) |
| Turns per day | 50 000 | 500 000 | 12.5 turns per Leo user |
| Peak turns/s | 2.9 | 29 | × 5 peak factor |
| Concurrent runs at peak | ≈ 35 | ≈ 350 | 12 s per run (draft p50) |
| Model calls per day | 125 000 | 1.25 M | 2.5 rounds per turn |
| Jev requests per day | ≈ 300 000 | ≈ 3 M | ≈ 2.2 per turn + ≈ 50 per Leo user per day for initiative and memory |
| Proactive signals per day | ≈ 400 000 | ≈ 4 M | mail ≈ 50 and events ≈ 50 per Leo user |
| Suggestions delivered per day | ≤ 24 000 | ≤ 240 000 | budget ≤ 6 per user per day |
| Thread rows per day | ≈ 150 000 | ≈ 1.5 M | ≈ 3 rows per turn (user, assistant, tool digests) |

The design must hold the right-hand column without a structural change.

---

## 3. Target architecture

### 3.1 Shape

```
                       ┌──────────────────── Application layer (channels) ─────────────────────┐
  Cabinet (Vite SPA) ──┤ HTTP /v1/agent/* + SSE │ WS /v1/ws/user │ voice (capture)  │ MCP (mcp)  │
  Native clients ──────┤ native compat routes   │ errand runner        │ proactive delivery      │
                       └──────────────┬──────────────────────────────────────────┬──────────────┘
                                      │ TurnCommand / ApproveCommand              │ Suggestion
                       ┌──────────────▼───────────────┐            ┌─────────────▼──────────────┐
                       │          Agent Core          │            │      Proactive Engine      │
                       │ run lifecycle · thread lease │◄───────────┤ signals → candidates →     │
                       │ LangGraph run graph          │ background │ decide → prepare → deliver │
                       │ Action Gateway (writes)      │    runs    │ → feedback                 │
                       └──┬───────────┬───────────┬───┘            └──────┬──────────────┬──────┘
                          │           │           │                       │              │
              ┌───────────▼──┐ ┌──────▼──────┐ ┌──▼─────────────┐  ┌──────▼──────┐ ┌─────▼──────┐
              │ Memory &     │ │ Tools &     │ │ Decision Layer │◄─┤ (same port) │ │ Errands    │
              │ Context      │ │ Skills      │ │ policies + Jev │  └─────────────┘ │ (errands)  │
              │ builder,     │ │ registry,   │ │ + fallbacks,   │                  └────────────┘
              │ memory, user │ │ toolsets,   │ │ decision       │
              │ state        │ │ playbooks   │ │ records        │
              └──────┬───────┘ └──────┬──────┘ └───────┬────────┘
                     │                │ ToolSpec        │ decide()
  ───────────────────┼────────────────┼─────────────────┼──────────────── Infrastructure ─────────
   home PostgreSQL (threads, actions, memory, suggestions) · Valkey (leases, run checkpoints,
   run event logs, user state) · TaskIQ (`agent` queue: runs) + outbox · scheduler · Qdrant ·
   provider port (F6): OpenRouter chat/embed/rerank/decisions(Jev) · Web Push · domain slices
```

**Where the Agent Core runs** ([ADR 0068](../../adr/0068-leo-agent-slice.md) AG-D12). A turn, and the resume after an approval, is a task of a dedicated TaskIQ queue `agent`, served by its own worker processes. The API authenticates, admits, commits the question and the `agent_runs` row, sends `run.started`, enqueues the run and streams the run's event log from Valkey; it holds no run state. Any API process can serve any run's stream, and a release of the API cuts no run.

### 3.2 The rule of separation

Each layer answers one question and owns the state for it:

| Layer | Answers | Never does |
|---|---|---|
| Application | *Who is asking, through which channel, and how is the answer carried?* | decide, reason, touch domain data |
| Agent Core | *What happens next in this run?* (lifecycle, loop, budgets, interrupts) | judge value or timing; execute a write outside the Action Gateway |
| Decision Layer | *Should this happen, when, and how strongly?* Answers come as typed probabilities. | generate text, call tools, grant a permission, weaken a hard rule |
| Memory & Context | *What does the model need to know now, within budget?* | decide what to do with it |
| Tools & Skills | *What can be done, and how is it done correctly?* | decide whether to do it; bypass the access policy |
| Proactive Engine | *Is there something worth the user's attention?* | write to user data; speak outside the delivery rules |

**Why the Decision Layer is separate** ([ADR 0026](../../adr/0026-leo-decision-layer-on-jev.md)). In the draft, the decisions "speak now?", "remember this?", "which tools?" and "how risky?" were scattered:

- static constants in `restraint.py`;
- regexes in `memory_link.py`;
- tariff filters in `registry.py`;
- nothing at all for risk.

None of them could be measured, calibrated, versioned or replayed. Making them one layer gives:

- one interface: decision point → policy → outcome;
- one record format;
- one place to calibrate thresholds;
- one fallback discipline.

That layer can then use a cheap calibrated model (Jev) without polluting the agent loop. The cost is one more slice and one more provider. The loop could still own decisions that are inseparable from generation. One such decision exists — choosing the next tool inside a round — and it stays with the generative model ([§6.6](#66-what-jev-does-not-decide)).

### 3.3 Slices and boundaries

Feature-first, as the target architecture §5 and CLAUDE.md require. Leo is a set of slices, not a monolith inside one slice:

| Slice | Owns |
|---|---|
| `agent` | Agent Core, Action Gateway, threads, runs, context builder, tool registry and skills runtime, HTTP/SSE channels; the native model proxy and the skills store |
| `decisions` | Decision Layer: policy registry, Jev adapter, thresholds, fallbacks, decision records. Platform-wide: also used by mail triage (`mail`), the hub signal (`hubs`) and others |
| `memory` | long-term memory, admission, retrieval, user profile core, personalization; Settings › Memory |
| `proactive` | signals, triggers, candidates, suggestions, delivery (`/v1/ws/user`, Web Push), feedback; the Today feed |
| `errands` | delayed actions; the native reminder routes |
| domain slices | their own tools, as `ToolSpec`s in their contracts: `notes`, `knowledge`, `files`, `commitments`, `hubs`, `tasks`, `calendar`, `mail`, `workspaces`, `support`, `studio` … |

- **Models and prompts are not a Leo slice.** The model registry, defaults and role assignments (platform tables), platform and user prompts and the personal context belong to `studio` ([ADR 0038](../../adr/0038-feature-slices-derived-from-the-product.md), slice map SM-5). The agent reads them through studio's `ModelRoutes` and `PromptResolver` contracts, as `capture`, `notes` and `memory` do. The build order of all slices is in the [slice map](../../plan/SLICE_MAP.md) §5.
- **Tool contract in core.** `core/agent_tools` holds the framework-light tool contract: `ToolSpec`, `ToolContext`, `EffectClass`, `PlannedEffect`, `Preview`, `ToolResult`. `FeatureParts` gains `agent_tools`, and composition hands every slice's specs to `agent`. The agent imports no domain slice. No domain slice imports the agent. This is the fix for C10 ([ADR 0029](../../adr/0029-leo-tools-owned-by-domain-slices.md)).
- **Clean Architecture inside `agent`:**
  - `domain/` holds the run state machine, action lifecycle, budgets and taint rules. It is pure.
  - `application/` holds the orchestrator, context builder and Action Gateway service, behind ports.
  - `infrastructure/` holds the LangGraph graph, the Valkey checkpointer and event log, and repositories.
  - `channels/` holds HTTP/SSE, tasks and subscriptions.

  LangGraph is infrastructure: no domain rule depends on it ([ADR 0023](../../adr/0023-leo-agent-core-layers.md)). **Its boundary** ([ADR 0068](../../adr/0068-leo-agent-slice.md) AG-D14): LangGraph is the frame of a turn — the loop model ⇄ tools, the pause for approval and its resume, the state passed between nodes. Its ready-made savers, prebuilt agents, `ToolNode`, model clients and memory or store are not used; rights, the Action Gateway, sources, taint, model calls through the provider port, storage and deletion are Shosai's own, the saver over LangGraph's public interface included. A saver that outgrows one file or needs LangGraph's internals is a separate decision for the owner.
- **import-linter.** The existing contracts already enforce slice independence. One new rule: `agent.domain`, `decisions.domain` and `memory.domain` import neither `langgraph` nor provider SDKs.

---

## 4. Components and responsibilities

| Component | Slice | Responsibility | State it owns |
|---|---|---|---|
| Channel adapters | agent, proactive | Authenticate; build `TurnCommand` through the one `PrincipalFactory`; map events to SSE or WS frames; native compatibility routes | none |
| `PrincipalFactory` | agent | The only builder of the run principal: user, home, org, roles, entitlements snapshot, switches, thread scope (personal / workspace / hub), the person's active memberships, consent flags. Fixes C4 | none |
| Admission | agent | Rate limit (GCRA), quota, abuse guard, spend reservation through the provider port, per-thread lease | Valkey lease |
| Run Orchestrator | agent | Run lifecycle (§5), deadlines, cancellation, post-turn work | `agent_runs` row; checkpoint while active or paused |
| Run graph | agent | LangGraph: `context → model ⇄ tools → propose → (interrupt) → respond`; a thin graph over application services | checkpoint (Valkey) |
| Context Builder | agent + memory | Budgeted, cache-stable prompt from segments (§7.3); untrusted wrapping; taint marking | none (inputs cached) |
| Tool Registry | agent | Aggregates `ToolSpec`s from slices; toolsets; schema generation; read dispatch with budgets | none |
| Action Gateway | agent | Proposals, approval, single execution, expiry, re-validation, audit through outbox. The only path to a write (§8.4) | `agent_actions` |
| Skills runtime | agent | Loads platform playbooks and user skills; activation; skill-scoped toolsets and output contracts | `agent_skills` |
| Decision Service | decisions | `decide(point, state)` → outcome; policies, thresholds, fallbacks, records, shadow mode | `decision_policies`, `decision_thresholds` (platform), `agent_decisions` (home, partitioned) |
| Memory Service | memory | Admission pipeline, supersession, retrieval, profile core, user controls | `memory_facts` |
| User State | proactive | Ephemeral attention state: presence per channel, current surface, in-meeting, focus, local time, notification budget | Valkey, TTL minutes |
| Signal intake | proactive | Outbox subscriptions and time triggers → typed signals (ids only) | `proactive_triggers` |
| Candidate generators | proactive | Pure, one per kind; features computed in code | none |
| Suggestion store and delivery | proactive | Suggestion lifecycle, channel arbitration, `/v1/ws/user`, Web Push, replay, seen/act/dismiss | `agent_suggestions`, `suggestion_deliveries`, push subscriptions |
| Errand runner | errands | Due rows → re-validate → execute the approved action or turn it into a new proposal | `errands` |
| Provider port | F6 (core) | Every model call, including Jev: cost row with effect key, spend guard, breaker, semaphore | `provider_costs` |

---

## 5. Agent lifecycle and control flow

### 5.1 Run states

A **run** is one execution of the agent for one input: a user turn, a background routine, or the resume after an approval.

```
            admit            first event                 write proposed
 requested ───────► running ─────────────► (streaming) ───────────────► awaiting_approval
     │ refused         │  │ deadline / error                                  │   │
     ▼                 │  ▼                                       approved     │   │ rejected / expired
  refused(4xx)         │ failed ◄─────────────────── resume ◄─────────────────┘   ▼
                       │                                                    completed
                       └── final answer ──► completed      cancel ──► cancelled
```

- One **active run per thread** (lease). A second turn on a busy thread gets `409 thread_busy`, unless it carries `supersede: true`. That flag cancels the running run first, the "stop and send" button. This fixes C2.
- **At most 2 interactive runs per user** across threads (abuse guard), plus background runs counted separately.
- Run deadlines:
  - interactive turn: 180 s;
  - background run: 300 s;
  - model stream stall: 45 s (§4.3);
  - read tool: 20 s by default, declared per tool.

### 5.2 Interactive turn, step by step

| # | Step | Where | I/O on the critical path (EU) |
|---|---|---|---|
| 1 | Authenticate; build principal (`PrincipalFactory`) | channel | token decode; entitlements from cache (Valkey 1–2 ms) |
| 2 | Admission: GCRA, quota, abuse, spend reservation (estimate from model and budget) | agent + provider port | Valkey 2 round trips |
| 3 | Acquire thread lease (`SET NX PX`, renewed every 10 s) | agent | Valkey 1 |
| 4 | One transaction: insert user message, insert `agent_runs` row, read thread summary + recent window. **Commit before streaming** (§14 rule 1) | agent | home DB 1 transaction (≈ 4 ms EU; ≈ 90–135 ms RU) |
| 5 | Send `run.started{run_id, thread_id, message_id}` | channel | — |
| 6 | **In parallel:** query embedding (shared by memory and knowledge), memory recall, `decide(turn.route)`, mentions and surface subject digests (batched through owner contracts), attachment digests | context builder | critical path = max(embedding ≈ 150–250 ms, Jev ≈ 160–300 ms) |
| 7 | Assemble prompt within budget (§7.3); choose model tier | context builder | CPU < 5 ms |
| 8 | Graph: `model` streams through the provider port → `text.delta`, `step.*` | run graph | provider |
| 9 | Read tool calls → parallel dispatch with budgets → results (digested over budget) → back to `model` | run graph | tools |
| 10 | Write tool calls → `propose`: Action Gateway plans the effect, computes the preview, runs `decide(action.friction)`, commits `agent_actions` → `action.proposed` → interrupt | run graph + gateway | 1 transaction + Jev |
| 11 | Final text → one transaction: assistant message, tool digests, run usage → `run.completed` → release lease | agent | 1 transaction |
| 12 | Outbox event `agent.turn_completed` (ids only) → background: memory admission, compaction, title, sampled online eval | tasks | off path |

The platform overhead budget is steps 1–7 plus 11, about 300 ms for EU users. Steps 6–7 run in parallel. A user who has never written gets no memory recall: a cached "has memories" bit skips the embedding.

### 5.3 Approval and resume

1. `POST /v1/agent/actions/{id}/approve {nonce, secret?}`. The Action Gateway moves `proposed → approved` with one conditional `UPDATE … WHERE status='proposed' AND nonce=…`, which makes the transition single-winner ([ADR 0025](../../adr/0025-leo-action-gateway.md)).
2. The gateway executes the items through their slices with idempotency keys `action_id:item` (§8.4). It records the per-item outcome, and the audit goes through the outbox.
3. If the run's checkpoint is alive, the graph resumes with the results. The model writes the epilogue in the same `run_id`, and the client receives `action.updated` then text.
4. If the checkpoint is gone, the action still executes, because it lives in the DB. The result is appended to the thread as a server message (trusted, structured), and the run is closed `completed` with reason `checkpoint_lost`. Before this design, the same loss restarted the dialogue (§8.1).

### 5.4 Background runs

A background run is what Leo does when nobody is typing: a meeting brief, a daily digest, a follow-up draft. It has these properties:

- It runs on the `default` queue as a task carrying `{home, user_id, skill, subject, trigger_id}`.
- Its principal is built from the stored user with `channel=background`. It gets **read toolsets only** and a token and cost budget per skill.
- It produces an **artifact** — a suggestion body, a draft, a brief — stored in `agent_suggestions`, or a **proposal** (`agent_actions`, origin `proactive`). It never produces a write.
- It is metered to the user's spend like an interactive run, but under a separate daily budget per user, so initiative cannot exhaust the user's interactive quota.

### 5.5 Multi-agent: no

One agent, one thread per scope, skills for specialisation, background runs for parallel work ([ADR 0023](../../adr/0023-leo-agent-core-layers.md)).

- **Not peer agents.** A supervisor with specialist agents multiplies model calls (2–4× tokens), adds a hand-off failure mode and fragments the user's sense of "one Leo". Specialisation is already achieved by a playbook with its own toolsets and instructions, at no extra round trip.
- **Revisit when** a skill needs more than its own toolsets and context window, or a measured eval shows a planner/executor split improves task success by more than its token cost.

---

## 6. Decision Layer and Jev

### 6.1 What Jev is, and what it is not

Jev is a **decision model** by TypeSafe AI, released on 2026-09-15. It is not a chat model and not a TypeScript library: the TypeScript and Python SDKs are only clients of an HTTP API. The backend stays FastAPI-only ([ADR 0021](../../adr/0021-public-site-on-nextjs-cabinet-on-vite.md)) and calls Jev through the F6 provider port.

**Request.** `POST https://openrouter.ai/api/alpha/decisions` takes:

- `model`, pinned to `typesafe/jev-1.13`, never the alias `~typesafe/jev-latest`;
- `state`, as text or JSON;
- `questions`, a map of named questions, each with `type`, English `instructions` and `criteria`:
  - `choice`: up to 255 options as a map of option name to description; the answer is the `choice`, its `confidence` and a probability per option;
  - `score`: an ordered scale of 2–10 levels, the lowest first; the answer is the expected level as a number (0 is the first level), its `confidence` and a probability per level keyed `"0"`, `"1"`…;
  - `noul`: optional `true` and `false` descriptions; the answer is `noul`, the probability that the proposition is true.

**Response.** It carries `answers`, `usage` (`input_tokens`, `output_tokens`, `cost`), the dated `model` snapshot (`typesafe/jev-1.13-20260917`) and an `id` (OpenRouter's API reference and Jev tutorial, read on 2026-10-13; the port's contract test holds a recorded answer).

**Properties that shape the design:**

| Property | Consequence here |
|---|---|
| Calibrated in aggregate, **not deterministic** (0.79 vs 0.84 on repeated calls) | Outcomes come from **bands with margins**, never exact values; a decision is recorded once and reused, never re-asked to "check" |
| Text only, no rationale, no tools, one round trip | The *why* comes from the policy's deterministic reason code and the features, not from the model |
| Weak at arithmetic, dates, counting, negation | **Features are computed in code** (minutes to the meeting, counts, ages) and given as values; questions avoid negations |
| 32 K context for state plus questions | The state builder has a hard budget, about 2 K tokens by default |
| $0.042 per M input tokens, output free; ≈ 160–300 ms per call by the published measurements (vendor or early figures) | Affordable on every turn; **latency is budgeted**, run in parallel, never sequential on the hot path |
| Early access, `alpha` endpoint, proprietary; data retention and DPA not published on the pages read | Contract test on the response shape; pinned snapshot; legal review before personal data is sent (§17 Q-3); a deterministic fallback for every policy |
| Language coverage not published | Every policy passes an evaluation in **all 16 platform languages** before it is enabled for anyone; otherwise it runs on its fallback for everyone (no branch by language, CLAUDE.md) |

**Exit path.** Open-weight decision models, Laya (multilingual, Apache-2.0) and Kev, expose the same `/v1/systemone` request shape through the Ollaya runtime. The adapter speaks that shape, so a self-hosted model behind the provider port is a configuration change plus an evaluation, not a redesign.

### 6.2 The model: decision point → policy → outcome

```
caller ──decide(point, subject, features, snippets)──► Decision Service
   1. resolve active policy version for the point
   2. hard pre-rules (deterministic; may short-circuit with a reason code)
   3. build state: typed features + bounded snippets (untrusted-wrapped)        ┐
   4. Jev call via provider port, deadline per point (questions batched)        ├ or fallback rule
   5. map answers to an outcome through calibrated bands                        ┘ on timeout / error / no consent
   6. post-rules (budgets, caps) — may only make the outcome more conservative
   7. record the decision (ids, features hash, probabilities, thresholds, version, source)
   8. return Outcome{value, reason_code, source: jev|fallback|rule, policy_version, decision_id}
```

- **A policy** is code, reviewed like code, versioned (`turn.route@3`). Its English question texts are registered in the model-facing English test. Each policy declares:
  - decision point, feature schema, questions;
  - band → outcome table;
  - hard rules, fallback rule, deadline;
  - whether it may run in shadow mode.
- **Thresholds** live in a platform table (`decision_thresholds`, EU home, data without an owner per §6), versioned per policy. Changing a threshold is a new version, not an edit.
- **Monotonic safety.** Steps 2 and 6 are deterministic and can only make an outcome *more* conservative. The Decision Layer never decides whether a confirmation is needed: that follows from the tool's effect class (§8.1). Jev can add friction, never remove it.

### 6.3 Decision points

| Point | Caller, when | Questions to Jev (one request) | Outcomes | Deadline | Fallback |
|---|---|---|---|---|---|
| `turn.route` | Agent, every turn, parallel with context | `noul` per candidate toolset (≤ 15), `choice` of skill (enabled skills + none), `score` complexity (4 levels), `noul` needs clarification | toolsets, skill, model tier, clarify-first flag | 350 ms | core toolset + toolsets of the surface, mentions and the thread's last 3 turns, then every other toolset the person may use while segment 2's cap holds; default tier; no skill (ADR 0068 AG-D7) |
| `action.friction` | Action Gateway, per proposal | `noul` the action matches what the user asked in this turn; `noul` the content was steered by third-party text; `score` impact | standard card · card with warning, screen-only approval · refuse and explain | 400 ms | card with warning, screen-only approval when the run's taint is external or worse or the write is irreversible; otherwise standard (ADR 0068 AG-D7) |
| `content.injection` | Context builder, per untrusted chunk entering a run (mail, web, foreign files, MCP output) | `noul` the text contains instructions addressed to an AI assistant | raise the run's taint level | 300 ms, async where possible | taint = external (the floor for any external content) |
| `memory.admit` | Memory, after a turn (background) | `choice` kind (preference, fact, relationship, goal, none); `noul` durable beyond a week; `noul` sensitive personal data; `noul` updates an existing fact (with neighbours in state) | store · ask the user · supersede · skip | 2 s | store only explicit requests made through the memory UI or the memory tool; skip the rest |
| `proactive.value` | Proactive, per candidate | `score` value to the user (5 levels); `score` urgency (4); `noul` the user already knows; `noul` actionable now | keep (with value, urgency) · drop | 2 s | the kind's static urgency, the draft's rules (`restraint.decide`) |
| `proactive.moment` | Proactive, at delivery time | `choice` now · next break · next session · digest · drop; inputs include the user-state features | deliver now · defer to moment · add to digest · drop | 1 s | defer to next session; quiet hours respected |
| `mail.triage` | `mail`, per new message | `choice` needs_you · fyi · low | triage label | 2 s | `importance.decide` rules from the draft |

`turn.route` replaces sending 130 schemas every round. Its miss rate is measured, and the model can recover a missed toolset with the meta-tool `load_toolset` (§8.2).

### 6.4 Calibration, shadow, replay

- **Offline calibration.** Each policy ships labelled synthetic datasets in all 16 languages. Its thresholds are fitted for a target precision per band. Release gates: per-language accuracy floor, expected calibration error ≤ 0.05, and no band with fewer than 50 examples.
- **Shadow.** A new policy version runs next to the active one on live traffic, is recorded, and acts on nothing. It is promoted when it matches or beats the active one on the online metrics of its point. The window is two weeks, or 5 000 decisions, whichever comes later.
- **Online calibration.** The decision record (probability, band) joins with the outcome the user gave: acted, dismissed, approved, rejected, corrected the memory. Reliability curves per policy and band are computed from ids and numbers only. No text leaves the home or enters the eval store.
- **Replay.** A record keeps the features and the hash of the state, not the state text. Changing thresholds can therefore be replayed exactly over past probabilities. Changing questions needs the synthetic sets.

### 6.5 Records and cost

`agent_decisions` lives in the home DB, monthly partitions, retained 90 days. Columns:

- `id`, `point`, `policy_version`, `subject_ref`, `features` (jsonb of numbers and enums);
- `state_hash`, `probabilities`, `outcome`, `source`, `latency_ms`, `cost`, `jev_request_id`, `created_at`.

Neither prompts nor state text are stored, per §16.8.

**Cost at the design point:**

- 300 000 requests per day × about 1 500 input tokens × $0.042/M ≈ **$19/day** (≈ $570/month);
- at 100 K DAU about $5 700/month.

The cost row is written by the provider port (inv-9), like any model call.

### 6.6 What Jev does not decide

- **Whether a confirmation is required.** That follows from the effect class (inv-12).
- **Access.** That is the access policy (inv-14).
- **The next tool inside a round.** That stays with the generative model. Routing narrows the menu; the model chooses from it. Splitting the per-step choice out would add a round trip per step and remove the model's ability to plan across steps.
- **What to say.** Jev generates no text.
- **Anything while consent is missing.** Without cross-border consent (nfr-14), the policy runs its fallback. The branch is by consent, not by language.

---

## 7. Memory and context

### 7.1 Kinds of memory

| Kind | What | Store | Authoritative? | Lifetime |
|---|---|---|---|---|
| Working | Run state: pending tool calls, rounds, references to context segments by hash | Valkey checkpoint | derived | while the run is active or paused (≤ action expiry, ≤ 24 h) |
| Conversation | Threads, messages, tool digests, rolling summary | home DB `agent_threads`, `agent_messages` | **yes** | until the user deletes the thread; tool payloads 30 days |
| Long-term memory | Facts, preferences, relationships, goals, procedures about the user | home DB `memory_facts` | yes | decay plus supersession; user controls |
| Profile core | Pinned facts, preferences, personalization, locale, timezone, answer language | derived from the above | derived | cached 10 min, invalidated on change |
| User state | Presence, surface, in-meeting, focus, local time, budgets | Valkey | derived | minutes |
| Knowledge | Meetings, notes, files, knowledge collections, context graph | owner slices (`notes`, `knowledge`, `files`, `commitments`) | not Leo's | owner's rules |

**Knowledge is not memory.** Mail, web pages and documents are searched, never memorised: memory holds what the user said and what was confirmed about them. Decisions and commitments with a lifecycle stay in the context graph (`commitments`), as the draft rightly decided (`recollection.py:3-13`).

### 7.2 Long-term memory

**Schema (`memory_facts`, home DB):**

| Group | Columns |
|---|---|
| Identity and content | `id` UUIDv7, `user_id`, `kind` (preference · fact · relationship · goal · procedure), `statement` (the user's language; it is user data, never an instruction), `subject_refs` (context-graph entity ids) |
| Provenance | `source_kind` (user_statement · meeting · settings · user_edit), `source_ref` (thread/message or meeting/segment ids) |
| Assessment | `confidence`, `sensitivity` (normal · sensitive) |
| Validity | `valid_from`, `valid_to`, `superseded_by` |
| Retrieval | `embedding`, `embedding_model` (fixes M4) |
| Lifecycle | `status` (candidate · active · forgotten), `pinned`, `last_confirmed_at`, `created_at` |

**Admission** (background, after a turn, [ADR 0030](../../adr/0030-leo-memory-v2.md)):

1. *Extract.* A cheap model reads the finished turn and proposes at most 3 candidate statements in a structured output. It reads only the **user's own messages**; tool results and external content are excluded. This replaces the draft's 16-language regex (M5).
2. *Judge.* `decide(memory.admit)` with the candidate and its 5 nearest neighbours: kind, durability, sensitivity, and whether it updates a neighbour.
3. *Supersede, don't merge.* An update closes the old fact (`valid_to`, `superseded_by`) and opens the new one. The newer fact wins, not the longer one, which fixes M3. History stays for "what did you know then".
4. *Ask when unsure.* Sensitive facts, and facts in the middle band, become `candidate`: shown as "Should I remember…?" in the panel or the memory page. Candidates are not used for answers.
5. *Respect the switches.* With `memory_enabled=false` or `no_logs`, nothing is extracted or stored, **on every path**: the meeting memory port, consolidation, extraction. This fixes M1, and an isolation test covers each writer.

Meeting recollections (the memory port called by `notes`) enter with `source_kind=meeting`. They are third-party speech, so they are always rendered as untrusted, with their source.

**Retrieval:**

- query embedding = last user message plus the previous assistant message's first 300 characters (one embedding, reused by knowledge search; fixes the "follow-up recalls noise" part of M4);
- top-40 by vector, then rank = similarity × recency weight × confidence;
- ≤ 12 facts and ≤ 600 tokens.

Recall does **not** refresh decay. Only use the model cites, or the user's confirmation, refreshes it.

**Forgetting:**

- decay by kind, as in the draft (fact 180 d, episode-like goals 30 d, procedure 365 d);
- soft forget, then purge after 180 d;
- consolidation runs per user on a cursor over all users (fixes M2), only for users with memory on, only when facts changed since the last pass.

**User controls:** list (cursor-paginated), edit, pin, forget one, forget all, accept or reject candidates, an off switch that keeps the data, export through account export (fr-8). Every fact shows its source.

### 7.3 Context Builder

**Budget.** The model's input window is split into segments with hard caps. Order goes from the most static to the most volatile, so provider prefix caching covers as much as possible ([ADR 0031](../../adr/0031-leo-context-budget-and-compaction.md)):

| # | Segment | Changes | Cap (default tier) | Notes |
|---|---|---|---|---|
| 1 | Platform system policy (versioned, English) | per release | 1 500 | role, rules, confirmation protocol, language directive |
| 2 | Tool schemas of the selected toolsets, canonical order | per thread, rarely | 4 000 | core toolset ≈ 600; draft: 20–25 K |
| 3 | Active skill playbook | per skill | 1 500 | |
| 4 | Profile core | per user, rarely | 600 | pinned memory, personalization, timezone, answer language |
| ↑ | **cache breakpoint** | | | explicit where the provider supports it |
| 5 | Thread summary | every few turns | 1 000 | rolling, written in the background |
| 6 | Recent messages, verbatim | per turn | 5 000 | questions and answers; earlier turns' tool rounds left out (agent step 6) |
| 7 | Volatile context | per turn | 2 500 | time to the minute, surface and subject digest, recalled memory, mentions, attachment digests, retrieved knowledge; all external text wrapped |
| 8 | User message | per turn | 4 000 | longer input becomes an attachment |

**Total ≈ 20 K at the caps, ≈ 10–12 K typical.** The draft measured about 30 K before any history (T1, T2).

**Rules:**

- **Tool results over budget** (default 1 500 tokens) are stored in full in `agent_tool_results` for 30 days. The context gets a digest: the same JSON with its longest lists cut to their first items and the full count of each, `truncated: true` and a `result_ref`. The `read_result(ref, cursor)` tool pages through the rest, wrapped with the label of the tool that produced it.
- **Earlier turns' tool rounds stay out of later turns** (amended 2026-10-24, agent step 6): within a run every round is whole; afterwards the answer carries what was learned, and its numbered sources carry the ids a follow-up needs. Stale tool output is the cheapest context to drop — it would crowd the questions and answers out of segment 6 and set compaction off after nearly every turn. The rounds stay in `agent_messages` for the run's record.
- **Compaction** runs after a turn, when the recent segment exceeds 70% of its cap. A cheap model folds the oldest turns into the thread summary. The hot path never waits for it; if compaction lags, the builder drops the oldest turns.
- **Attachments** are stored and referenced. Their digest stays available on later turns (fixes the draft's per-turn loss), and the full text is read through `read_result`.
- **Time and surface go last**, never in segment 1. The draft's minute-level `now_line` at the top broke every prefix cache (T2).

### 7.4 Untrusted content and taint

- **One wrapper, v2.** A per-run random boundary token, escaping of any boundary-like sequence inside the data, and a provenance label from a closed set (`mail`, `web`, `file:foreign`, `file:own`, `meeting:speech`, `task:foreign`, `memory`, `mcp:<server>`, `skill:user`; `task:foreign` is text in tasks the person did not write — a colleague's, a meeting's through extraction, a Jira user's, [ADR 0059](../../adr/0059-tasks-one-store-boards-action-items-and-jira.md)). Labels are never attacker text. This fixes A4.
- **Taint level of a run:**
  - `none`: only the user's own words and own structured data;
  - `external`: any external text entered the context;
  - `suspicious`: `content.injection` fired.

  Taint is monotonic within a run and drives the following:
  - **egress tools** — web search, image generation, external MCP reads — require a confirmation card when taint ≥ external;
  - **write cards** show "prepared using content from …", and voice approval is disabled;
  - **memory admission** ignores the run when taint = suspicious.

  This breaks the injection → exfiltration chain (A4) without a classifier being the only defence.
- **Server text written into a thread** — reminder seeds, action results — is structured. External parts inside it are wrapped, which fixes A5.

---

## 8. Tools and skills

### 8.1 The tool contract

A domain slice declares its tools in `contracts.agent_tools` as `ToolSpec`s:

| Field | Meaning |
|---|---|
| `name` | namespaced, `notes.search` |
| `toolset` | `notes`; ≤ 8 tools per toolset |
| `description` | English; registered in the model-facing test |
| `input` / `output` | Pydantic models; JSON schema generated; arguments **validated**, invalid → error result (fixes "invalid JSON → `{}`") |
| `effect` | `read` · `egress` (reads but sends data outside: web, image, external MCP) · `write` · `client` (navigate, theme) |
| `reversibility` | for writes: `reversible` · `compensable` · `irreversible` |
| `cost_class` | `free` · `metered` |
| `entitlement`, `switch` | required gate and user switch, checked at planning and at execution |
| `result_budget` | token cap of the result in context |
| `provenance` | the label of the untrusted text the result carries, from §7.4's closed set (`meeting:speech`, `file:foreign` …); none for the user's own words and data. A result may narrow it — the user's own file where the spec says a colleague's — but never remove it. The agent wraps the result with it and raises the run's taint |
| `timeout` | per call |
| `plan(args, ctx) → PlannedEffect` | writes only: **freezes the exact targets** (ids, counts) at proposal time |
| `preview(planned, ctx) → Preview` | server-computed, i18n keys and parameters; never the model's prose |
| `execute(planned, ctx, idempotency_key) → Result` | the slice runs its own transaction under the principal's `TenancyScope` (RLS), checks access again, applies the effect **only to the planned targets**, and records the key and the outbox audit event in the same transaction |
| `invalidates` | client query domains to refresh after success (fixes W2 drift) |

**Why it is shaped this way:**

- The agent never holds a DB session of another slice. The access policy runs inside the owner (inv-14).
- Preview and execution cannot diverge, because execution is bound to the plan (fixes A8).
- Idempotency is a property of every write (fixes A1).

### 8.2 Toolsets and routing

About 14 toolsets, each owned by a slice:

- meetings, notes, knowledge, people & commitments, calendar, mail, tasks, files, hubs;
- web (egress);
- reminders and errands;
- Leo settings and memory;
- support and account;
- studio.

**Always on:** the **core toolset**, about 600 tokens:

- `workspace.search`, a cross-domain search returning typed refs;
- `read_result`;
- `load_toolset`;
- `navigate`;
- `ask_user`, a structured clarification.

Each arrives with its first consumer ([ADR 0068](../../adr/0068-leo-agent-slice.md) AG-D10): `read_result`, `load_toolset` and `navigate` with the agent's tools; `workspace.search` with `knowledge`; `ask_user` with a cabinet UI for a structured question.

**Routing** combines these signals:

- `decide(turn.route)`;
- the toolsets of the current surface (a meeting page brings `notes`);
- the toolsets of mentioned objects;
- toolsets used in the thread's last 3 turns (sticky);
- skill-required toolsets.

If the model needs more, `load_toolset(name)` adds the schemas for the next round. That costs one extra round, so its rate is a routing quality metric with an alert at > 5% of turns.

### 8.3 Execution

- **Reads and egress** run in parallel, at most 8 calls per round; further calls of the round are refused. Each has its own timeout, and its result is capped by `result_budget`. Errors become typed error data the model can explain; a call of a tool not offered, or with arguments its schema refuses, never runs. Calls pass a per-process bulkhead sized below the database pool, so a burst waits for a connection instead of failing for one.
- **Writes and egress join with their cards**: writes with the Action Gateway (agent step 9a), egress in agent step 13b. An egress call made once the run's taint is external or worse is proposed as a card like a write (one card waits at a time), runs once on approval as the person, and its kept result becomes that call's answer when the epilogue resumes — its sources numbered among the run's, its text wrapped with the tool's label; an untainted run's egress call runs at once.
- **Egress** additionally requires a card when taint ≥ external (§7.4), and is metered.
- **Rounds:**
  - soft limit 4: after it, reasoning is forced on and the planner prompt asks to conclude;
  - hard limit 10: the last round has no tools.
- **`finish_reason=length`** is detected. Text is marked truncated; a tool call with truncated JSON is rejected with an error result instead of being executed with `{}` (fixes C6).
- **External MCP tools** (`mcp`, client side):
  - namespaced `mcp.<server>.<tool>`;
  - descriptions sanitised: control characters stripped, capped at 500 characters, shown to the user at connect time;
  - input schemas capped at 4 KB;
  - read-only-declared tools are `egress`, never plain `read`;
  - all others are `write` through the Action Gateway (fixes A7).

### 8.4 Action Gateway

The **only** path to a write ([ADR 0025](../../adr/0025-leo-action-gateway.md)).

**Table `agent_actions`** (home DB):

| Group | Columns |
|---|---|
| Identity and origin | `id` UUIDv7, `user_id`, `org_id`, `thread_id`, `run_id`, `origin` (turn · proactive · errand · mcp) |
| State | `status` (see below), `nonce` |
| Items | `items` jsonb: tool, planned effect, redacted args, preview shown, per-item outcome |
| Risk | `friction` (from `action.friction`), `taint` |
| Time | `not_before` (errands), `expires_at` |
| Approval | `approved_at`, `approved_via` (web · voice · native · inbox) |
| Audit | `created_at`, `updated_at` |

**State machine:**

```
proposed ──approve──► approved ──claim──► executing ──► succeeded | partially_succeeded | failed
    │ reject / expire / superseded                          │ crash during an item
    ▼                                                       ▼
 rejected | expired | superseded                    outcome_unknown (never auto-retried)
```

**Rules:**

1. **Single winner.** Each transition is one conditional `UPDATE … RETURNING`, so a double click, two tabs, or voice racing the screen all yield exactly one executor.
2. **Idempotency.** Item key = `action_id:index`. Slices store processed keys in the effect's transaction; repeating a key returns the stored result. External effects (sending mail through a connector) follow a write-ahead discipline:
   - commit `executing(item)`;
   - call the provider with its idempotency key where it has one;
   - commit the outcome.

   A crash in between leaves `outcome_unknown`. That item is never retried automatically, and the user is told "may have been sent — check before retrying". At-most-once wins over at-least-once, as inv-12 demands.
3. **Expiry.** Interactive proposals expire after 1 h. Proposals produced by initiative expire with their suggestion (≤ 24 h). Errand approvals are valid until their `not_before` plus the lateness tolerance (§9.5).
4. **Secrets** go through a one-time Valkey vault (`GETDEL`, TTL 5 min). The secret is submitted only with the approval request, never by voice, never in a checkpoint, a message or an action row. The vault is built with the first tool that needs a secret (ADR 0068 AG-D10).
5. **Batches** apply item by item, with honest partial success; they are never presented as atomic.
6. **Audit.** Each item's effect emits an outbox event `agent.action_item.executed` (ids, tool, status, codes; no content) in the slice's transaction — core's `ActionItems.once` claims the item key in the effect-key ledger, runs the effect and writes the event together, so a slice's `execute` cannot forget either. The `agent` slice consumes it into `agent_audit` (monthly partitions, 12 months, append-only role). Rejections and expiries are audited by the gateway itself.

**Confirmation channels:**

| Channel | How the user approves | Limits |
|---|---|---|
| Web panel card, approvals inbox | button with the `nonce` | — |
| Native (later) | same endpoint | — |
| Voice | The server reads back the server preview. The **server-side transcript** of the user's next utterance must be judged an approval by `noul` "the user approved the action that was just read back" (calibrated in 16 languages) **and** the voice model must call `confirm(action_id)`. | `reversible` and `compensable` actions only; not when taint ≥ external or friction = screen-only; irreversible actions and secrets go to the screen (push to the open cabinet). Fixes A2 |
| MCP (external client) | A write returns `pending_approval{action_id, approve_url}`; the human approves in the cabinet's inbox or through a push | Persistent-injection sinks (personalization, prompts, context) are not exposed for writing over MCP at all. Fixes A3 |
| Errand | Approved at scheduling; re-validated at run time (§9.5) | — |

### 8.5 Skills

A skill is a **versioned package** that shapes behaviour without granting rights ([ADR 0028](../../adr/0028-leo-skills-and-autonomy-levels.md)):

| Field | Platform skill (curated) | User skill (SKILL.md, pinned commit) |
|---|---|---|
| Instructions | English, reviewed, registered in the model-facing test | untrusted text, wrapped, subordinate to policy; scanned at install with `noul` "attempts to change the assistant's permissions or safety rules" → install refused |
| Toolsets | declared; may request any the user has | none of its own; uses the routed toolsets |
| Output contract | optional (brief template, draft schema) | none |
| Autonomy ceiling | declared (e.g. `prepare` for a background brief) | `answer` only |
| Eval suite | required | — |

- **Activation:** explicit (`/skill`, a chip in the UI), by `turn.route`, or by a proactive routine (a trigger bound to a skill; the morning brief = `daily_brief` at the user's 08:30).
- **First platform skills:** `meeting_prep`, `meeting_follow_up`, `daily_brief`, `inbox_triage`, `weekly_review`, `research_web`, `data_analysis` (deterministic statistics, as the draft's CSV insights).

This fixes M6: in the draft, skills never reached Leo.

---

## 9. Proactivity and autonomy

### 9.1 Principle

Leo speaks first only when three things hold:

- there is **value** — the user would act on it or is glad to know;
- it is **timely** — now, or at a better moment that will come;
- the user has **room** for it — attention state and budgets.

The first two are judgements, made by Jev under calibrated policies. The third is rules plus a judgement. Silence is the default, and every refusal is recorded with a reason ([ADR 0027](../../adr/0027-leo-event-driven-proactivity.md)).

### 9.2 Autonomy levels

| Level | Leo may | Confirmation | Example |
|---|---|---|---|
| A0 Observe | compute signals and candidates | — | "topic X came back 3 times" |
| A1 Inform | surface a suggestion in its own surfaces | — | chip on the meeting page; card in the Leo feed |
| A2 Prepare | create Leo-owned artifacts with read-only tools | — | draft reply, meeting brief, proposed task list, all inside the suggestion |
| A3 Propose | create an action card | the user approves (inv-12) | "Create these 4 tasks in project Y?" |
| A4 Execute | run an approved action | already approved; re-validated if delayed | errand sends the approved email at 9:00 |

Beyond these rules:

- **No level writes without approval.** Writing into Leo's own suggestion store is not a write to the user's data. Creating a draft in the user's mailbox *is* a write, because it is an external side effect.
- **Standing approvals** ("always file my notes into folder X") would be confirmation given in advance. They conflict with the literal reading of inv-12, so they are **not designed** here; see §17 Q-4.
- **The user's initiative setting** (`off` · `reserved` · `active`) caps the level of initiative: `off` = A0 only, `reserved` = A1–A2 with a low budget, `active` = A1–A3.

**Insistence** is a separate axis, kept from the draft:

| Insistence | Meaning | Daily budget | Quiet hours |
|---|---|---|---|
| `explicit` | the user set this moment (a reminder) | not used | ignored, because the user chose the time |
| `requested` | a rule the user asked for (a watched sender) | own budget | respected |
| `initiative` | Leo's own idea | ≤ 6 deliveries and ≤ 2 interruptions per day | respected |

### 9.3 Pipeline

```
outbox events ─┐                    ┌─ hard rules: settings, muted kind, entitlement, consent, dedup
time triggers ─┼─► signal ─► candidate generator ─► decide(proactive.value) ──keep──► prepare (A2,
state changes ─┘   (ids)     (pure, features)        drop → record                   background run,
                                                                                     only if kept)
                ┌──────────────────────────────────────────────────────────────────────┘
                ▼
        suggestion(pending) ─► decide(proactive.moment) at each "moment opened" ─► deliver
                                   │ defer → wait for next moment          │ digest → daily brief
                                   ▼                                       ▼
                              feedback: seen · opened · acted · approved · dismissed(reason) · snoozed · muted
                                   └──► calibration of value and moment policies
```

**Signals are event-driven,** never global scans (fixes P3). Inputs:

- outbox subscriptions:
  - `notes.meeting.notes_ready`, `notes.meeting.ended` (`notes`);
  - `mail.received` (`mail`, from connector sync);
  - `calendar.event_changed` (`calendar`), `tasks.task.due_changed`, `tasks.task.assigned` (`tasks`; `tasks.task.completed` and `tasks.task.deleted` withdraw a task's candidate, ADR 0059);
  - `commitments.due`, `commitments.topic_looped` (`commitments`);
  - `connectors.broken` (`connectors`), `hubs.topic_looped` (`hubs`), `support.replied` (`support`), `errands.failed`;
- **time triggers** as rows in `proactive_triggers` (`run_at`, kind, subject), run by the scheduler with `FOR UPDATE SKIP LOCKED`, the same way as errands (§12). Calendar changes upsert the pre-meeting triggers; the morning brief is one row per user per day;
- **user-state transitions** from Valkey — meeting ended, came online, focus ended — open a *moment*: the user's deferred queue is evaluated.

**Rules that fix the audit's findings:**

- **Content is prepared only for kept candidates.** That stops the spend the draft wasted on rejected mail summaries (P7).
- **Withdrawal.** A cancelled meeting or a completed task withdraws its candidate through its event (fixes P6).
- **One reminder system.** Calendar email reminders, meeting-soon and errands become kinds of the same pipeline, with one budget and one quiet-hours rule (fixes P6).

### 9.4 Delivery and feedback

**Surfaces** fit the new cabinet, which has no proactive UI yet ([§13.3](#133-cabinet-shosai)):

- in-context chips on the subject's page (meeting, mail, hub, task);
- the Leo feed ("Today");
- a message in the scope's thread for conversational follow-ups;
- push or desktop only for `explicit`, or for `initiative` with urgency ≥ high and the moment = now.

**Channel arbitration by *seen*, not by socket presence** (fixes P5):

- A suggestion is `delivered` when a client receives it and `seen` when the client reports it visible: page visible and the element in the viewport.
- If an urgent one is not seen within 3 minutes, it escalates to push or desktop.
- A background tab no longer swallows everything.

**Feedback** is first-class UI on every suggestion: act, dismiss with an optional reason (not useful · wrong time · wrong), snooze, mute this kind. Feedback writes `suggestion_feedback`, and it feeds:

- the hard fatigue rule: 3 dismissals of one kind in 7 days → that kind drops to `reserved` for 14 days;
- the calibration of value and moment (§6.4).

**Durability:**

- every suggestion is stored, replayed on `hello` (24 h, ≤ 20) and expires explicitly;
- nothing is lost because nobody was online (fixes P5);
- native clients keep `reminder.due` / `reminder.settled` for `explicit` reminders unchanged.

### 9.5 Errands

Errands are rows run by the scheduler (§12; no Temporal):

| Kind | Payload | At run time |
|---|---|---|
| `remind` | text | deliver as an `explicit` suggestion |
| `act` | `action_id` of an action approved at scheduling | re-validate, then execute through the Action Gateway |
| `routine` | skill + subject | background run (A2) → suggestion |
| `follow_up` | condition + subject (e.g. "if no reply by Friday") | evaluate the condition through the owner contract; if met → candidate |

**Re-validation of `act`** checks that:

- the principal still has access and entitlement;
- the targets in the plan still exist and are unchanged where the plan pinned them (e.g. the recipient);
- lateness ≤ the tolerance the user saw at scheduling (default 15 min).

If any check fails, the errand becomes a **new proposal** delivered to the user, and is never silently executed late (fixes P4).

**Single execution** comes from the Action Gateway: the errand row only points at the action. **Failures** become a durable `errands.failed` suggestion. Failed rows stay visible 30 days (amendment §16).

---

## 10. State management and persistence

| Store | Data | Kind | Home | Retention | Loss |
|---|---|---|---|---|---|
| home PostgreSQL | `agent_threads`, `agent_messages` (monthly partitions, UUIDv7) | authoritative | user's / company's home | thread until deleted; a workspace's threads hidden when membership ends and erased 7 d later unless it is restored (ADR 0068 AG-D3) | backup, PITR (nfr-2) |
| home PostgreSQL | `agent_tool_results` (monthly partitions) | authoritative | home | read for 30 d, partitions dropped after 2 months | — |
| home PostgreSQL | `agent_feedback`, `agent_eval_cases` (ADR 0068 AG-D13) | authoritative | home | a rating with its answer; a case only with `improve_models` consent, erased with the rating, the consent, the thread or the account, and after 12 months | — |
| home PostgreSQL | `agent_runs` (partitions) | authoritative telemetry: ids, model, tokens, cost, latencies, outcome, policy versions | home | 90 d | — |
| home PostgreSQL | `agent_actions` | authoritative | home | 30 d after a terminal state; audit stays 12 months | — |
| home PostgreSQL | `agent_audit` (partitions) | authoritative, append-only | home | 12 months | — |
| home PostgreSQL | `memory_facts` with pgvector embeddings (ADR 0033) | authoritative | home | user controls; forgotten → purge 180 d | — |
| home PostgreSQL | `agent_suggestions`, `suggestion_deliveries`, `suggestion_feedback`, `proactive_triggers`, `proactive_settings`, `push_subscriptions` | authoritative | home | suggestions 90 d; feedback 12 months | — |
| home PostgreSQL | `errands` | authoritative | home | finished 24 h, failed 30 d | — |
| home PostgreSQL | `agent_decisions` (partitions) | telemetry | home | 90 d | — |
| home PostgreSQL | `agent_skills` (user-installed) | authoritative | home | with the user | — |
| EU home (platform) | prompts, skills catalogue, model registry, `decision_policies`, `decision_thresholds` | platform data without owner (§6) | EU | versions retired, not deleted | — |
| Valkey | thread leases; run checkpoints of **active and paused runs only**; run event logs (stream per run, ≤ 2 000 events, TTL 1 h); vault; user state; "has memories" bits | derived, ≤ 24 h | EU (accepted exception, §6) | TTL | in-flight runs fail; paused actions survive in the DB |
| Qdrant | knowledge and meeting windows (`knowledge`, `notes`) | derived | EU | — | rebuild |

**What changes against §8.1 "Leo state"** ([ADR 0024](../../adr/0024-leo-threads-in-the-home-database.md)):

- The conversation is no longer only a Redis checkpoint with "loss restarts the dialogue". It is authoritative in the home DB, so Russian users' conversations stay in Russia, unlike the draft.
- Valkey holds only what is in flight. A completed run deletes its checkpoint. That cuts the derived copy of Russian users' text in the EU from up to 24 h of every thread to minutes of active runs, and Valkey memory from ≈ 2.5 GB (50 000 threads × 50 KB) to tens of MB.
- The one-time key that guards writes becomes the row state of `agent_actions`.

**Checkpoint discipline.** State holds references (segment hashes, message ids), not the frozen system prompt. Writes go per superstep with channel-version deduplication (the draft wrote full snapshots, C8). Deletion of an account or thread deletes its keys through the deletion registry (§14 rule 7).

**Volume at the design point:**

- `agent_messages` ≈ 150 000 rows/day × ≈ 1.5 KB ≈ 225 MB/day ≈ 80 GB/year before the 30-day payload trim;
- ≈ 30 GB/year after the trim, split 80/20 between the RU and EU homes.

This is below the transcript tables (1.9 TB/year) and needs no new store.

---

## 11. Reliability, safety, observability, evals

### 11.1 Failure behaviour

| Failure | Behaviour |
|---|---|
| Model provider slow or down | Breaker per (provider, model) — not per provider (fixes C9); fallback to the next model of the same tier from the registry; one retry before the first byte; "model unavailable" error frame only when the tier is exhausted |
| Jev slow, down or contract changed | Each policy's fallback; `decision_fallback_total{point,reason}`; contract test failure blocks the release |
| Valkey down | New interactive runs refused, 503 `agent_unavailable` (expensive AI fails closed, §13.2); approvals still execute (DB); proactive defers delivery |
| Link to the Russian DB lost | Leo 503 for Russian users (§11 flow 8); EU unaffected |
| Qdrant down | Knowledge search falls back to PostgreSQL keyword search (§4.3); memory unaffected (pgvector in the home DB, ADR 0033) |
| A domain slice's tool fails | Typed error result to the model; writes record the item `failed` with a code |
| Agent worker dies mid-run | Lease expires (30 s); the run is marked `failed{process_lost}` by a sweep, never re-run by the queue; the user message is already persisted, so "retry" re-runs; paused actions are unaffected |
| API process dies or is released while streaming | The run continues in its agent worker; the client resumes from `Last-Event-ID` on another API process |
| Process dies mid-execution of an approved action | The item stays `executing` past its lease → `outcome_unknown`; the user is told; never auto-retried (§8.4) |
| Client disconnect | The run continues; the answer is persisted; the client resumes from `Last-Event-ID` or reloads the thread |
| Unknown exception in a run | Always a terminal `run.failed{code}` (fixes C5); traced and counted |

### 11.2 Safety layers

| Layer | Mechanism |
|---|---|
| Who | One `PrincipalFactory`; principal in the runtime context, never in model-controlled state; thread scope (personal / workspace / hub) applied by `ToolContext` to **every** tool (fixes A10): reads cover every space the person may access, each checked by the access policy, and every result carries its space; the scope ranks its own space first and is the default target of writes; a write into another space names that space in its preview ([ADR 0039](../../adr/0039-one-account-per-person-with-workspaces.md)) |
| What data | Each slice's access policy and RLS in `execute`; search hits re-checked in PostgreSQL (inv-14, §7) |
| What actions | Effect class decides confirmation; Action Gateway is the only write path; single winner; idempotency |
| Which text is trusted | Wrapper v2 with provenance; taint level per run; memory and skills untrusted; server-written thread entries structured |
| What leaves | Egress tools metered and, when tainted, confirmed; model output Markdown never auto-loads images or remote resources (kept from the draft) |
| Input and output filters | Abuse guard and safety filter on input; output filter on streamed text, windowed so it does not block streaming |
| Secrets | One-time vault; never in state, messages, logs, spans or audit |
| Audit | Per item through the outbox; arguments redacted to field names and hashes; no content (fixes A11) |

### 11.3 Observability

- **Traces.** Root span `agent.run` (`run_id` = trace attribute, linked to the HTTP request), with children:
  - `agent.admission`, `agent.context`;
  - `decision.<point>` (policy, version, source, outcome, latency; no state);
  - `llm.call` (model, tier, input/cached/output tokens, cost, TTFT, `finish_reason`);
  - `tool.<name>` (effect, outcome, result tokens);
  - `action.execute`.

  Trace context crosses into background runs, proactive tasks and outbox events (§16.2).
- **Metrics** (labels from closed sets only):

  | Area | Metrics |
  |---|---|
  | Turns | `agent_turns_total{channel,outcome}`, `agent_platform_overhead_seconds`, `agent_ttft_seconds{tier}`, `agent_context_tokens{segment}` |
  | Cost | `agent_turn_cost_usd{tier}` |
  | Tools and actions | `agent_tool_calls_total{toolset,effect,outcome}`, `agent_load_toolset_total`, `agent_actions_total{origin,outcome}`, `agent_approval_seconds` |
  | Decisions | `decision_requests_total{point,source,outcome}`, `decision_latency_seconds{point}` |
  | Proactivity | `proactive_suggestions_total{kind,stage,outcome}`, `proactive_seen_to_act_seconds` |
  | Memory | `memory_admissions_total{outcome}` |

  Platform overhead = run wall time − provider time − tool time in other slices.
- **`agent_runs` rows** give per-user answers ("why did user X wait 18 s?") through ids, never metric labels. This fixes C12.
- **Invariant monitors** (must stay 0, page on any):
  - an action item executed twice (same key, two effects);
  - an item executed without `approved`;
  - a provider call without a cost row (inv-9, Jev included);
  - a suggestion with `initiative` delivered inside quiet hours;
  - memory written for a user with memory off.
- **SLOs** (§16.3 additions):

  | SLO | Objective | Alerting |
  |---|---|---|
  | Leo platform overhead | ≤ 500 ms p95 EU | paged |
  | Run platform failures | < 1% | paged |
  | Approved actions | ≥ 99% executed or reported `failed` with a code within 30 s | paged |
  | Proactive precision | — | tracked, not paged |

### 11.4 Evaluation

| Suite | What | Where | Gate |
|---|---|---|---|
| Trajectories | Per skill and toolset: tool choice, arguments, order, final answer; mocked tools; rule checks + LLM judge | CI on synthetic data | no regression > 3 points on any suite; tool-choice accuracy ≥ baseline |
| Safety | Injection corpora through each untrusted channel (mail, web, foreign files, meeting speech, memory, MCP descriptions, user skills); assert no unapproved write, and no egress after untrusted text without its card | CI | 0 violations |
| Confirmation invariants | Property tests (Hypothesis) over the Action Gateway: concurrent approvals, crashes at each step, expiry, replays | CI, real PostgreSQL | 0 double executions |
| Multilingual parity | The trajectory and decision suites in all 16 languages | CI (nightly) | per-language floor |
| Decision calibration | Per policy: accuracy per band, ECE, coverage per language | CI on threshold or question change | ECE ≤ 0.05 |
| Context budget | Token count per segment on fixtures; prefix stability (byte-identical segments 1–4 across turns) | CI | caps hold |
| Cost | Tokens and model calls per scenario | CI | no increase > 10% without a recorded reason |
| Online | Shadow decisions; sampled LLM-judge scores on 1% of runs (in the plane, scores only stored); "Useful / Not useful" under answers; approval and rejection per tool; suggestion outcomes | production | dashboards; weekly review |
| Donated cases | Rated turns shared with the person's `improve_models` consent and no workspace source, kept in the person's home: "Not useful" ones as a set a change must improve, "Useful" ones as a guard set (ADR 0068 AG-D13). Replayed where they live — today's model answers from the tool results the case kept, a judge compares the answer with the rated one — and every case read is a row of the admin's audit log; the report keeps verdicts only | `shosai agent eval cases replay` on the host (the suites of made-up people run in development only), before a release of a prompt, model or toolset change | no regression on the guard set |

Prompts, policies, toolset descriptions and model choices are versioned, and every change runs the suites. The draft's live tool-choice eval was a skipped stub (`tests/test_agent_tool_choice_evals.py:228-244`). Here the suites are gates.

---

## 12. Performance, scalability, cost

**Latency budget** (EU, warm caches), against L-N1:

| Step | Budget |
|---|---|
| Auth, principal, admission, lease | 15 ms |
| Persist user message + read window (1 transaction) | 10 ms |
| Parallel context (embedding ‖ Jev ‖ digests) | 300 ms |
| Prompt assembly | 5 ms |
| Finalize (1 transaction) | 10 ms |
| Tool dispatch overhead per call, excluding the tool's own I/O | 5 ms |
| **Total platform** | **≈ 350 ms** |

For Russian users, add 3 transactions × 45 ms ≈ 135 ms of round trip; this is accepted per §20. The draft measured about 2.3 s.

**Throughput:**

- At 10 K DAU: ≈ 3 turns/s peak and ≈ 35 concurrent streams. At 100 K DAU: ≈ 29 turns/s and ≈ 350 concurrent streams.
- A run is I/O-bound. Runs execute in worker processes of the dedicated `agent` queue, at most 48 concurrent runs each ([ADR 0068](../../adr/0068-leo-agent-slice.md) AG-D12): 1 process at 10 K DAU and about 8 at 100 K DAU, by configuration with the N+2 rule. **Measured (agent step 17)** in production's shape — the API and one agent worker as their own processes on the local stack, the model a double over HTTP answering ≈ 800 tokens over 8 s after a tool round, histories of 100 messages: at 3.6 turns/s on the worker (the design point's 29 turns/s over 8 workers) the platform's time is p50 96 ms and p95 138 ms; at 8 turns/s p95 319 ms; at 12 turns/s (48 runs at once) p95 0.8–1.0 s. A worker spends ≈ 0.2 s of CPU per turn, so one worker serves about 8 turns/s within L-N1 and the 8 workers of 100 K DAU keep a twofold margin. A count of running runs across the fleet, kept in Valkey, answers 429 `agent_busy` when the workers are full, so a turn never waits in the queue behind a full fleet. The run task has no automatic retry. Agent workers stop with a 200 s grace and are handed over without a gap; the API keeps its 30 s.
- The API serves the streams: one blocked `XREAD` per process tails all the run logs its clients follow, so an open stream costs it kilobytes and no Valkey connection of its own. The queue's pickup adds a few milliseconds before the first token; it is measured and counted in the platform overhead.
- Model concurrency is bounded by the provider-wide semaphore (§12).

**Valkey:**

- a run's event log is ≈ 12 KB for an answer of 800 tokens with a tool round (measured, agent step 17); it lives an hour after its last write while the run goes on and ten minutes after its end, when only a reconnecting stream reads it (an hour after the end kept every turn of the last hour: ≈ 104 000 logs, ≈ 1.3 GB at 100 K DAU);
- event logs ≈ (350 running + 29 turns/s × 600 s) × 12 KB ≈ 0.2 GB at 100 K DAU and ≈ 25 MB at 10 K; leases and fleet counts are bytes; a checkpoint exists only for a run paused on a card;
- user state ≈ 40 000 × 1 KB = 40 MB.

**Database per turn:**

- 4 transactions on the hot path (measured, agent step 17): the API's check before admission (an `Idempotency-Key` replay, the thread, consent, settings) and its write of the question and the run, the worker's read of the context and its write of the end; plus the provider port's cost row for each model call (F6) and 1 per approval;
- background work: 1–3 transactions for memory, compaction and runs.

At 29 turns/s (100 K DAU) that is ≈ 120 tx/s on the hot path and ≈ 70 cost rows/s, against the RU home's pool of 10 per API process and 5 per worker at 45 ms per round trip. This fits, and it is watched by the existing pool alerts.

**Proactive:**

- ≈ 400 000 signals/day at 10 K DAU ≈ 5/s average, 25/s peak. Event volume scales with activity, not with the number of users × the scan frequency (P3).
- Only the outbox subscriptions of §9 pass the outbox (meeting, mail, calendar, task, commitment, connector, hub, support and errand events); time triggers and user-state transitions do not. The relay drains each home's outbox in passes of 100 within a 15 s budget per tick, so a peak is absorbed without a structural change; a sustained > 20 events/s per home, or ticks cut by the budget, is the revisit trigger of the target architecture §12, decided on measurements (F1 audit OD-4).
- Time triggers are rows that fall due; the scheduler enqueues only due ones.

**Cost model** (assumptions: default tier input $0.30/M and output $1.20/M tokens, 50% of the prefix cached at a 75% discount; these are placeholders until F6 sets prices):

| Item | Draft shape | This design | Per day at 10 K DAU |
|---|---|---|---|
| Input tokens per turn (2.5 rounds) | ≈ 30 K × 2.5 = 75 K | ≈ 11 K × 2.5 = 27 K | 50 000 turns → 1.35 B tokens ≈ $260 (draft ≈ $1 100) |
| Output tokens per turn | ≈ 800 | ≈ 800 | ≈ $48 |
| Jev | — | ≈ 300 000 requests | ≈ $19 |
| Embeddings (one per turn, shared) | 2 per turn | 1 per turn | small |
| Proactive preparation | per scanned mail, before gates | only kept candidates, ≤ 6 per user per day | ≤ 24 000 background runs, budgeted per skill |

**Levers in order of effect:**

1. toolset routing;
2. cache-stable prompt order;
3. result digests and compaction;
4. tiering, where `turn.route` complexity sends simple turns to the fast tier;
5. preparing only kept candidates.

Each lever has a metric (§11.3) and an eval gate on cost (§11.4).

---

## 13. Integration

### 13.1 Backend: ports Leo uses and provides

| Direction | Port | Owner | Use |
|---|---|---|---|
| uses | model routes and prompts: `ModelRoutes`, `PromptResolver` | `studio` | model choice per role, fallbacks, system and feature prompts |
| uses | provider port: `stream_chat`, `complete`, `embed`, `rerank`, **`decide`** (Jev), with effect key, spend reservation | F6 | every model and decision call (inv-9, §14 rule 4); fixes C3 |
| uses | identity: token → principal claims | `identity` | `PrincipalFactory` |
| uses | entitlements, spend balance | `billing` | admission, tool gates |
| uses | access policy, inside each slice's `execute` and read services | `workspaces` | inv-14 |
| uses | `ToolSpec`s and event types | the domain slices of §3.3, `errands` | tools, signals |
| uses | search; people and commitments | `knowledge`; `commitments` | `workspace.search`, knowledge, people and commitments |
| provides | memory port: `record_recollections(meeting)` | memory → `notes` | meeting facts with provenance |
| provides | agent port: `run_voice_turn`, `confirm_by_voice` | agent → `capture` | one thread for text and voice |
| provides | decision port: `decide(point, …)` | decisions → any slice | mail triage (`mail`), hub signal (`hubs`) |
| provides | registry projection for MCP | agent → `mcp` | external MCP tools under the same gateway |
| provides | user-context port for live answers | memory → `capture` | profile core for `/v1/ws/realtime` `ask` |

### 13.2 Wire contract

**New, web class, free to design with the cabinet (ADR 0022)** — [ADR 0032](../../adr/0032-leo-stream-protocol-v2.md):

| Route | Purpose |
|---|---|
| `GET /v1/agent/threads?scope=&cursor=` · `POST /v1/agent/threads` · `GET/PATCH/DELETE /v1/agent/threads/{id}` | threads per scope (personal / workspace / hub), title, archive |
| `GET /v1/agent/threads/{id}/messages?cursor=` | history, cursor-paginated (§10 contract rules) |
| `POST /v1/agent/threads/{id}/turns` → `text/event-stream` | a turn; JSON body `{text, surface, mentions[], upload_ids[], options}` plus `Idempotency-Key` (client message id) so a retried POST does not duplicate the turn; attachments uploaded first through presigned uploads |
| `GET /v1/agent/runs/{id}/events` (SSE, `Last-Event-ID`) | resume a dropped stream (fixes C5, H3 of the client audit) |
| `POST /v1/agent/runs/{id}/cancel` | stop |
| `GET /v1/agent/actions?status=proposed&cursor=` · `POST /v1/agent/actions/{id}/approve` · `POST /v1/agent/actions/{id}/reject` | approvals inbox and cards |
| `GET /v1/agent/suggestions?surface=&subject=` · `POST /v1/agent/suggestions/{id}/feedback` | feed, in-context chips, feedback |
| `GET/PUT /v1/agent/settings` | initiative level, quiet hours, channels, model, answer language, style, switches |
| `GET/POST /v1/agent/memory` · `PATCH/DELETE /v1/agent/memory/{id}` · `DELETE /v1/agent/memory` · `POST /v1/agent/memory/{id}/accept` | memory controls |
| `GET/POST/DELETE /v1/agent/skills…` | skills |
| `PUT/DELETE /v1/agent/messages/{id}/feedback` | "Useful / Not useful" under an answer (ADR 0068 AG-D13) |
| `/v1/admin/agent/*` | Leo in the admin panel: the operator's threads and turns, read-only toolsets over platform aggregates (ADR 0068 AG-D5) |

The full contract — turn body, refusals, page shapes — is in the [agent plan](../../plan/slices/agent.md) §3.3.

**SSE events** — every event has `id: <seq>` and a 15 s heartbeat comment:

| Event | Payload | Replaces in the draft or the new UI's mock |
|---|---|---|
| `run.started` | `run_id, thread_id, message_id` | — |
| `step.started` / `step.completed` / `step.failed` | `id, seq, activity, tool?, toolset?, detail?, duration_ms?, error?` | `step` / `step_start`, `step_end` |
| `text.delta` | `text` | `token` / `text` |
| `sources` | the cumulative `LeoSource[]` (kind, id, title, space, locator, quote, highlight), numbered by position; the answer cites `[n]` (ADR 0068 AG-D1) | the new UI's mock `sources` |
| `artifact` | `kind, ref, alt` and the kind's fields: `chat_digest` (`workspace_id, chat_id`; agent plan AG-R1); `chart` and `image` with the admin's analytics, `file` with its first producer (ADR 0068 AG-D10) | `image` (no base64 in the stream) |
| `client.action` | `{navigate: {to}}` (`set_theme` dropped, ADR 0068 AG-D10) | `action{navigate,set_theme}` |
| `action.proposed` | the action as stored, server preview, friction, taint note, `invalidates` | `action{action_proposal}` |
| `action.updated` | id, status, per-item outcome, `invalidates` | `action_result` |
| `run.paused` | `action_id` | — |
| `run.completed` | `message_id, outcome (answered · stopped), truncated?` | `done` |
| `run.failed` | `code` (i18n key on the client) | `error` |

**Native, unchanged** (D1 `native` class; nfr-12):

- `/v1/ai/chat/stream` and `/v1/ai/vision/analyze`: the raw model proxy. It is not Leo, but it is served by `agent` through the provider port.
- `POST /v1/proactive/reminders/{errand_id}/done`, `POST /v1/errands/{errand_id}/snooze`.
- `WS /v1/ws/user`:
  - `hello`, `ping`/`pong`, `ack`;
  - `reminder.due{nudge_id, deliveries, title, body, errand_id, preview, created_at, turn_text?}`, `reminder.settled{nudge_id}`.

  New suggestion frames are additive (`agent.suggestion`, `agent.action_updated`). Clients ignore unknown frames (§10).
- The deep link `/cabinet/leo?reminder=<id>` is redirected by the cabinet.

**Dropped:**

- `/v1/ai/agent/{chat,act,prewarm,reminder-context}` and `/v1/ws/voice`: web class. D1 records that the Swift kit's Leo module reaches users only through the unshipped iOS app.
- `/v1/proactive/feed*`: `unused`, FM-5.
- The old memory, personalization and proactive settings routes: replaced by `/v1/agent/*`.

### 13.3 Cabinet (Shosai)

The new design already has the Leo panel:

- contexts `personal` / `workspace` / `hub`;
- a step timeline;
- an "approval" badge;
- client-held history and an NDJSON mock.

This design turns that into a real client and adds what is missing. The frontend skills apply (composition, React performance, view transitions, interface guidelines).

| Surface | Change |
|---|---|
| Leo panel | threads from the server; scope = the panel context; a "Recent chats" menu (ADR 0068 AG-D2); streaming from SSE with resume; the step timeline keeps its ledger reducer (dedup by id, order by seq, terminal states final); answers with their sources and spaces; "Useful / Not useful" under each answer (AG-D13) |
| Action card | compound component (`ActionCard.Root/Header/Preview/Items/Actions`); shows the server preview, friction warning, taint note; approve/reject; per-item outcome; replaces the "needs approval" badge |
| Approvals inbox | new: pending actions across threads, errands and MCP |
| Leo feed ("Today") | new: suggestions, daily brief, feedback controls |
| In-context chips | owner features expose a slot; Leo fills it from `GET /v1/agent/suggestions?subject=` (composition over coupling) |
| Settings › Leo | the existing contract fields plus initiative level, quiet hours, channels, push devices, memory candidates |
| Memory page | list, edit, pin, forget, candidates, source of each fact |

**Engineering rules:**

- **Render cost.** A token re-renders only the live message. The run store (Zustand) is keyed by run, with selector subscriptions, and deltas are batched per animation frame. Markdown is incremental: finished blocks are memoised and only the tail block re-parses. That fixes W1. The renderer is the cabinet's own, on `marked`'s lexer; it never renders raw HTML, renders links only with `https`, `http`, `mailto` or a cabinet path, loads no remote resource, and is tested on unfinished Markdown and XSS (§17 Q-2, ADR 0068 AG-D6).
- **No hand-mirrored registries.** Types come from OpenAPI, and activity labels come from server activity codes plus i18n with a generic fallback. Cache invalidation follows `invalidates` from `action.updated` (fixes W2).
- **Lazy loading.** The panel, voice and Markdown extras load on first open, prefetched on hover or ⌘I (fixes W4).
- **Accessibility.** The panel is a dialog: focus moves in and out, Escape closes. The feed is `role="log"` and announces completed messages, not tokens. Mentions use combobox semantics (fixes W3).
- **Errors.** Errors are never written into the conversation (fixes W5). On logout, nothing of the thread stays in the browser beyond the HTTP cache.

---

## 14. Architecture decision records

| ADR | Decision | Replaces in the draft |
|---|---|---|
| [0023](../../adr/0023-leo-agent-core-layers.md) | Leo is one agent built as six separated layers across slices; LangGraph is infrastructure inside the agent slice; no multi-agent | one service package with tools reaching into every domain |
| [0024](../../adr/0024-leo-threads-in-the-home-database.md) | Threads and messages are authoritative in the home database; Valkey keeps only in-flight run state | client-held history + Redis checkpoint with 24 h TTL |
| [0025](../../adr/0025-leo-action-gateway.md) | Action Gateway: durable proposals, single-winner approval, frozen plans, idempotent execution, `outcome_unknown` instead of retries | interrupt in the checkpoint + 60 s Redis claim |
| [0026](../../adr/0026-leo-decision-layer-on-jev.md) | Decision Layer as a slice: versioned policies over Jev through the provider port, deterministic hard rules and fallbacks, records and calibration | constants, regexes and tariff filters scattered in code |
| [0027](../../adr/0027-leo-event-driven-proactivity.md) | Proactivity from outbox events, time-trigger rows and state transitions; value and moment judged per candidate; seen-based delivery; feedback | global 5-minute scans, static urgency, dead feedback |
| [0028](../../adr/0028-leo-skills-and-autonomy-levels.md) | Autonomy levels A0–A4 with no write before approval; skills as versioned packages that never grant rights | skills bound only to role prompts; implicit autonomy |
| [0029](../../adr/0029-leo-tools-owned-by-domain-slices.md) | Tools are `ToolSpec`s owned by domain slices, aggregated by composition; toolsets with routing | 130 tools in the agent package, all sent every round |
| [0030](../../adr/0030-leo-memory-v2.md) | Memory v2: admission by extraction + decision, supersession, provenance, untrusted rendering, switches on every path | regex capture of raw messages, longest-text merge |
| [0031](../../adr/0031-leo-context-budget-and-compaction.md) | Budgeted, cache-stable context with digests, `read_result` and background compaction | message-count cap, unbounded context files |
| [0032](../../adr/0032-leo-stream-protocol-v2.md) | `/v1/agent/*` with SSE events with ids and resume; native routes kept | `/v1/ai/agent/*` without resume; NDJSON mock |
| [0068](../../adr/0068-leo-agent-slice.md) | The agent slice's decisions: sources from tools, past conversations, a workspace's threads after membership ends, routes before studio, Leo in the admin panel, the cabinet's Markdown renderer, rules before Jev, eval gates, parts built with their consumer, skills, feedback and donated cases, LangGraph's boundary; turns on a dedicated `agent` queue's workers | sources on sample data; client-held history; no rating |

---

## 15. Implementation plan

Phases follow dependencies, not calendar dates. **P0** is needed for a usable Leo, **P1** for the target experience, **P2** follows. Each phase is a set of steps of the named Leo slice (or of the named slice) under the slice prompt in `docs/plan/prompts/S-feature-slice.md`. Each step ends with its gates, tests and evals.

| Phase | Priority | Content | Depends on | Exit criteria |
|---|---|---|---|---|
| 0. Decisions | P0 | Done 2026-10-08: this document, ADRs 0023–0033 and the amendments (§16) accepted. Left: OpenAPI for `/v1/agent/*`, SSE event schema (`agent` plan); `ToolSpec` contract (F6) | — | contract files committed |
| 1. Prerequisites | P0 | F6 provider port with `decide`, cost rows, spend reserve/settle, breaker per model; `identity`; F2 cabinet on Vite with MSW mocks of `/v1/agent/*` | F1 (done) | F6 and `identity` done |
| 2. Core | P0 | `agent` slice: threads, messages, runs; lease; run graph (model ⇄ reads); `PrincipalFactory`; context builder v1 (segments 1, 2, 4, 6–8); core toolset; SSE with resume; spans, metrics, `agent_runs`; eval harness with the trajectory and budget suites; model-facing registration. Cabinet: panel on the real API | 1 | turn works end to end on one slice's read tools (the first ready slice, e.g. `notes`); platform overhead measured ≤ 500 ms EU |
| 3. Action Gateway | P0 | `agent_actions`, plan/preview/execute contract, approvals, expiry, vault, outbox audit; action card and approvals inbox; property tests for inv-12 | 2 | invariant suite green; 0 double executions under fault injection |
| 4. Decision Layer | P0 (parallel to 3) | `decisions` slice: policies, Jev adapter, thresholds, fallbacks, records, shadow; synthetic 16-language sets; `turn.route` and `action.friction` in shadow, then active | 1; legal Q-3 before personal data reaches Jev | calibration gates pass; routing miss (`load_toolset`) ≤ 5% |
| 5. Memory v2 | P1 | `memory` slice: facts, admission, supersession, retrieval, profile core; compaction; memory page; the memory port for `notes` | 2, 4 | switches proven on every writer; safety suite green for memory |
| 6. Tool coverage | P0→P1 | Each domain slice ships its toolset in its own plan (§3.3); the agent provides the contract and evals | 2, 3 and the slice | trajectory suite per toolset |
| 7. Proactivity | P1 | `proactive` slice: signals from outbox, trigger rows, candidates, `proactive.value` and `proactive.moment`, suggestions, delivery via `/v1/ws/user` (native frames kept) and Web Push, seen-based arbitration, feedback; feed and chips; `daily_brief` and `meeting_prep` skills | 4, 5, 6; F6 scheduler | precision and dismissal measured; budgets and quiet hours proven by tests |
| 8. Errands | P1 | `errands` on the Action Gateway; re-validation; native reminder routes | 3, 7 | late or changed errands become proposals in tests |
| 9. Skills | P1 | Platform playbooks; SKILL.md import with install scan; routing by `turn.route` | 4, 6 | per-skill eval suites |
| 10. Voice and MCP | P1 | the agent port for `capture` with voice confirmation rules; the `mcp` registry projection with pending approvals | 3, 4 | A2 and A3 regressions covered by tests |
| 11. Hardening | P2 | Load test to the 100 K column; chaos (Valkey, Jev, provider, RU link); cost dashboards; calibration review cadence; standing approvals if the owner decides Q-4 | all | SLOs met under load |

**Critical path:** F6 → core → Action Gateway → tool coverage. The Decision Layer and the cabinet run in parallel. Proactivity is the largest P1 block and the most dependent one.

---

## 16. Proposed amendments to the target architecture

Accepted by the owner on 2026-10-08 and applied to [ARCHITECTURE.md](../ARCHITECTURE.md) in the same change.

| § | Today | Proposed |
|---|---|---|
| §8.1 "Leo state" | checkpoints in Redis, TTL 24 h; loss restarts the dialogue; writing action guarded by a one-time key | threads and messages in the home DB (authoritative); Valkey holds checkpoints of active and paused runs and run event logs only (≤ 24 h); writes guarded by `agent_actions` row state (ADR 0024, 0025) |
| §8.1 | — | new entities: `agent_actions`, `agent_suggestions` (+ deliveries, feedback), `proactive_triggers`, `memory_facts`, `agent_runs`, `agent_decisions` |
| §8.1 "Errand and schedule" | finished errands after 24 h | failed errands kept 30 days, visible to the user |
| §8.2 | partitioned tables list | add `agent_messages`, `agent_runs`, `agent_decisions` |
| §5 domains | `agent`, `errands` | add `decisions`, `memory`, `proactive` |
| §4.2, §18.2 AI providers | OpenRouter for chat, vision, embeddings, rerank, web search | add decisions: Jev (TypeSafe AI) through OpenRouter's Decisions API, pinned snapshot |
| §12 | errands rows run by the scheduler | add proactive time triggers as rows run by the scheduler the same way |
| §16.3 | Leo: platform overhead per turn | add: run platform failures < 1%; approved actions executed or failed with a code ≤ 30 s ≥ 99%; proactive precision tracked |
| §16.4 | monitors | add: action item executed twice; executed without approval; initiative delivered in quiet hours; memory written with memory off |
| §22 | legal review list | add TypeSafe AI (Jev) as a subprocessor: retention, DPA, cross-border consent coverage |

---

## 17. Open questions for the owner

| # | Question | Recommendation | Blocks |
|---|---|---|---|
| Q-1 | Where do memory vectors live: pgvector in the home DB or Qdrant? | **Decided 2026-10-08:** pgvector in the home DB for memory; Qdrant for knowledge and meetings ([ADR 0033](../../adr/0033-vectors-pgvector-for-memory-qdrant-for-knowledge-and-meetings.md)) | — |
| Q-2 | Streaming Markdown in the cabinet: `streamdown`, another library, or our own incremental renderer? (CLAUDE.md "Undecided") | **Decided 2026-10-23:** our own incremental renderer on `marked`'s lexer, with no raw HTML, allowed link schemes only and tests on unfinished Markdown and XSS; measured on a long answer in the agent plan's step 7 ([ADR 0068](../../adr/0068-leo-agent-slice.md) AG-D6) | — |
| Q-3 | Jev legal and contract: TypeSafe's retention and DPA are not published on the pages read; the endpoint is `alpha` | until resolved, Jev runs only on synthetic data and in shadow over features without text; every policy runs on its fallback | phase 4 activation |
| Q-4 | Standing approvals (a confirmation given once for a class of writes)? | not now; revisit with acceptance data from phase 7, as an explicit amendment of inv-12 if ever | — |
| Q-5 | The agent's name after the rebrand: does "Leo" stay? | keep "Leo" in code and prompts (`agent` slice); the visible name is i18n | copy only |
| Q-6 | Voice approval of reversible actions by the server-verified transcript (§8.4) — acceptable, or screen-only for every write? | accept for reversible and compensable actions; screen for the rest | phase 10 |
| Q-7 | The brief named "Jev from TypeScript AI". The model found is **Jev by TypeSafe AI** (OpenRouter `typesafe/jev-1.13`); TypeScript appears only in its SDKs. Is that the intended product? | proceed with TypeSafe Jev | phase 4 |

---

## 18. Sources

- Jev: [OpenRouter — What is Jev](https://openrouter.ai/blog/insights/what-is-jev/), [How to use Jev](https://openrouter.ai/blog/tutorials/how-to-use-jev/), [Jev on OpenRouter](https://openrouter.ai/docs/guides/community/jev), [developersdigest — Jev guide](https://www.developersdigest.tech/blog/how-to-use-jev-typesafe-guide-2026). Latency and cost figures there are vendor or early measurements; this design budgets for them and requires our own measurement in phase 4.
- Agent patterns: the `agent-architecture` skill (21 agentic design patterns), used for the choices on routing, tool use, memory, human-in-the-loop, guardrails, evaluation, resource-aware optimisation and prioritisation.
- System design method: the `system-design-method` skill and its building blocks (requirements, estimates, trade-offs, failure modes).
