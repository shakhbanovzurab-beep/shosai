# Rewrite plan: draft → shosai

How Shosai is built in `/root/shosai`, with the draft (`/root/whisperer`) as a reference. The rules are in [.claude/CLAUDE.md](../../.claude/CLAUDE.md) ("Rewrite from the draft" and everything else) and the architecture in [docs/design/ARCHITECTURE.md](../design/ARCHITECTURE.md). This plan does not repeat them; it orders the work.

- **Status of every work package:** [STATUS.md](STATUS.md).
- **The feature slices, their scope, data, routes, dependencies and build order:** [SLICE_MAP.md](SLICE_MAP.md) ([ADR 0038](../adr/0038-feature-slices-derived-from-the-product.md)).
- **Prompts to start an agent:** [prompts/](prompts/).

---

## 1. How the work runs

1. The user starts **one agent per work package, each in a new session**, opened in `/root/shosai` with read access to the draft:

   ```bash
   cd /root/shosai && claude --add-dir /root/whisperer
   ```

2. The first message of the session is the package's launch line from [section 6](#6-launch-lines). It points the agent to its prompt file in [prompts/](prompts/).
3. The agent works, runs the checks, reports, and waits. It commits only after the user says «Принято».
4. A large package spans several sessions: every feature slice, and F1, F2, F4, F5 and F6. The user starts it with the same launch line each time; the first session writes the package plan, each later session implements the next step of that plan ([prompts/README.md](prompts/README.md), "Session mode for multi-session packages").
5. Several packages may run in parallel sessions when their dependencies are done ([section 4](#4-dependencies-and-parallelism)).

## 2. Facts every agent needs

| Fact | Value |
|---|---|
| Draft | `/root/whisperer` — read only. Production today runs the draft at `whisperer.one`. |
| Final version | `/root/shosai` — the only place that changes. |
| Domain of v2 | **https://shosai.tech** — today the test environment (staging): its own databases, storage and secrets, separate from the draft's production on `whisperer.one` ([ADR 0040](../adr/0040-shosai-tech-is-the-domain.md)). |
| Hosting now | RU/EU data homes and EU Valkey are not available yet. Develop and test on local containers; the code stays home-aware (CLAUDE.md, "Hosting constraints now"). |
| Local tooling | uv 0.12.21, Python 3.14.7 (uv-managed), Node.js 26.10.0, npm 11, Docker 29.8 with Compose 5.5, ffmpeg. |
| Production data | Never read or write the draft's production database or storage. `backend/.env` of v2 holds production values of the draft — do not use them. |

### Done means, for every package

- The package's own definition of done (in its prompt) holds.
- Every check in CLAUDE.md passes: stage checks, tests, gates 100/100, mypy strict, CI green after push.
- Behaviour follows the product — the new web UI, the philosophy, the target and Leo architectures (CLAUDE.md "Goal"); the native routes and frames of shipped clients stay compatible.
- [STATUS.md](STATUS.md) is updated in the same commit.
- Decisions that CLAUDE.md or the target architecture leave open are recorded as ADRs in `docs/adr/`, and the user has confirmed them.

## 3. Phases and work packages

### Phase 0 — Baselines from the draft

These packages read the draft and produce the references that every later package is checked against. They write no application code.

| ID | Package | Output |
|---|---|---|
| D1 | API and WebSocket contract baseline | `contracts/draft/`: the draft's OpenAPI, the WebSocket frame catalogue, and the list of endpoints and frames the shipped native clients use |
| D2 | Visual baseline and parity harness | A route inventory, recorded API fixtures, and a Playwright harness that screenshots the draft and v2 frontends against the same fixtures and compares them. Since 2026-10-07 a record of the draft's screens and a coverage list, not a gate ([ADR 0022](../adr/0022-new-web-design-replaces-draft-parity.md)) |
| D3 | Data inventory and mapping | `docs/plan/DATA_MAPPING.md`: every draft table and bucket prefix mapped to its v2 place, including the home and company model |
| D4 | Feature map | `docs/plan/FEATURE_MAP.md`: every draft backend module and frontend feature mapped to a v2 slice; anything proposed for removal listed for the user's decision. Since 2026-10-13 the inventory of the draft, a reference: [SLICE_MAP.md](SLICE_MAP.md) replaced its cut as the plan of record |

### Phase 1 — Foundation

| ID | Package | Output |
|---|---|---|
| F1 | Backend foundation | `backend/` project: `core/`, `composition/`, `entrypoints/` for `api`, `ws`, `workers`, `scheduler`; configuration; home-aware database sessions; Valkey, Redis cache and S3 clients; structured logging and telemetry; the error envelope; the model-facing-English test; import-linter contracts; test-database claiming; health endpoints |
| F2 | Frontend foundation | The cabinet in `frontend/`: the new web UI moved from Next.js to a Vite SPA without visual change — React Router, TanStack Query, `use-intl` with 16 locales, a data layer generated from the OpenAPI contract, the sample API removed, npm scripts required by CI ([ADR 0021](../adr/0021-public-site-on-nextjs-cabinet-on-vite.md)) |
| F3 | Local environment | `compose.dev.yaml`: PostgreSQL 18 with pgvector as **two databases standing in for the RU and EU homes**, Valkey, Redis cache, Qdrant, and later LiveKit; prepared test databases; one command to start and one to reset |
| F4 | Delivery to staging | Dockerfile (one image, four roles), production Compose, NGINX, TLS, image registry, `scripts/release.sh`, CI build and deploy to https://shosai.tech |
| F5 | Observability | OpenTelemetry Collector, Prometheus, Alertmanager, Loki, Tempo, Grafana configuration per target architecture §16, including the `alerting` domain |
| F6 | Platform services | The AI provider port that writes a cost row for every call, with spend control and the abuse guard; the email port; the periodic-job registry on `schedule_runs`; Jev decisions (`decide`) through the same port with a breaker per model ([ADR 0026](../adr/0026-leo-decision-layer-on-jev.md)); the agent tool contract `core/agent_tools` through which every slice exposes tools to Leo ([ADR 0029](../adr/0029-leo-tools-owned-by-domain-slices.md)). Added by D4 (decision FM-4) because most slices need them from their first step |

### Phase 2 — Feature slices

Each slice is a vertical piece of one business capability, built from scratch: backend slice and frontend slice with the same name, tests, compatibility of the native routes and frames it owns with D1, its screens of the new web UI working on the API ([ADR 0022](../adr/0022-new-web-design-replaces-draft-parity.md)). The cut was derived from the cabinet and the philosophy, not from the draft's modules ([ADR 0038](../adr/0038-feature-slices-derived-from-the-product.md)). Each slice's card in [SLICE_MAP.md](SLICE_MAP.md) §4.2 holds its scope, owned data, native and external routes, dependencies, events and Leo tools; the inventory row of every screen is in §2. The ID of a slice is its name; its plan is `docs/plan/slices/<name>.md`.

| ID | What it does for the user | Wave |
|---|---|---|
| `identity` | One login for web and desktop; profile and privacy; export and deletion of everything; operator accounts and roles | 1 |
| `workspaces` | Shared team space: members, teams, roles, seats, projects, sharing; the access policy and audit for every slice (its core first, its screens in wave 3) | 1, 3 |
| `billing` | Plans, entitlements, usage meters, payments, seats, company invoices (entitlements first, payments in wave 3) | 1, 3 |
| `files` | The user's files, uploads and quota — the one path for bytes | 1 |
| `meetings` | Every recorded meeting becomes notes, transcript, map and facts; share links | 1 |
| `capture` | Live capture, live answers and live translation on the desktop | 1 |
| `agent` | Leo: threads, runs, tools, Action Gateway, skills, the native model proxy | 1 |
| `tasks` | One task list: boards, meeting action items, workspace tasks, Jira | 2 |
| `connectors` | One registry of connected services and their grants | 2 |
| `calendar` | One calendar over connected calendars, with meetings and focus time | 2 |
| `knowledge` | Indexing and search over files, notes, sources and meetings | 2 |
| `commitments` | People, decisions, promises and open topics across all meetings | 2 |
| `hubs` | One place per client or piece of work that watches what is unresolved | 2 |
| `decisions` | Leo's Decision Layer over Jev, also used by mail and hubs | 2 |
| `memory` | What Leo knows about the user, visible and correctable | 2 |
| `proactive` | Leo's initiative: signals, suggestions, the Today feed, push | 3 |
| `errands` | Delayed Leo actions and reminders | 3 |
| `mail` | Leo reads the inbox, says what needs the user and drafts replies | 3 |
| `studio` | How Shosai's AI behaves: models, prompts, personal context | 3 |
| `mcp` | Shosai as an MCP server; external MCP servers for Leo | 3 |
| `support` | Tickets and newsletters between operators and users | 4 |
| `releases` | Desktop builds, staged rollout, downloads | 4 |
| `telemetry` | Client errors as issues; product events; the satisfaction survey | 4 |
| `rooms` | Shosai video rooms with per-speaker transcription, broadcasts and the room whiteboard | 4 |
| `site` | The public site in `site/` on Next.js ([ADR 0021](../adr/0021-public-site-on-nextjs-cabinet-on-vite.md)) and the public pages of shared links, SEO per [docs/seo/STRATEGY.md](../seo/STRATEGY.md) | any time after F6 |

The home screen, the Meetings overview, the Settings dialog and the admin dashboard are composition screens: each widget calls its owner's API; no backend slice aggregates them.

### Phase 3 — Data migration and cutover

| ID | Package | Output |
|---|---|---|
| M1 | Data migration | Tooling that moves the draft's production data into the v2 schema per D3, rehearsed on a copy, with verification of counts, invariants and money |
| M2 | Cutover | Runbook and rehearsal: maintenance window ≤ 30 min (nfr-12), v2 in production on `shosai.tech`, the native clients' `whisperer.one` API pointed at v2, rollback path, native clients verified against production |

## 4. Dependencies and parallelism

```text
D1 D2 D3 D4                       (done; references)
F3 ── F1 (per the F1 audit) ── F6 (steps 1–9) ── wave 1 ── wave 2 ── wave 3 ── wave 4
      F2 ──────────────────────────────────────┘
F1 F2 F6 ── site                  (any time, in parallel)
F1 F2 ── F4 ── F5                 (steps 1–5 of F4 and 1–6 of F5 need only F1)
identity ── F6 step 10
all slices + D3 ── M1 ── M2
```

The waves, from [SLICE_MAP.md](SLICE_MAP.md) §5 — each gives the user a working Shosai one step larger:

| Wave | Goal for the user | Slices, in default order | Exit |
|---|---|---|---|
| 1. Record, remember, ask | A person signs in on the web and on the desktop, records or uploads a meeting, reads its notes and asks Leo about it | identity → workspaces (core: access policy, RLS, audit) → billing (entitlements, minutes meter) → files → meetings → capture → agent (core, Action Gateway) | the shipped desktop clients run end to end on v2 staging: sign-in, capture, upload, notes; Leo answers over meetings and files with SSE and approvals |
| 2. Track and connect | The home screen is real: tasks, calendar, recent notes, hubs that watch what is unresolved | tasks → connectors → calendar → knowledge → commitments → hubs; decisions and memory in parallel | action items are tasks on one board; meetings join calendar events; search and Leo cover knowledge; hubs fill themselves |
| 3. Team and initiative | Workspaces work together; Leo speaks first when it is worth it | workspaces (screens) → billing (payments, seats, invoices) → proactive → errands → mail → studio → mcp | invite, share, pay per seat; Today feed and reminders; the inbox triaged |
| 4. Operations and cutover readiness | Operators run the platform; every native and external route answers | support → releases → telemetry → rooms | the D1 gate passes and lists no native route as not served (`backend/tests/composition/native_routes_not_served.json` is empty; external routes are each slice's own design, F1 audit OD-2) |

- The fixed dependencies are technical: F1 (as the F1 audit decides), F2, F3 and F6 steps 1–9 come before any slice; `identity` comes first, because every other slice needs an authenticated user; `workspaces` core comes before any slice with shareable resources, so they are written against the access policy from their first step (nfr-15, inv-14).
- Within a wave, a later slice may start when the contracts it needs are published; the order above is the default path of [prompts/BACKEND-next-step.md](prompts/BACKEND-next-step.md), which prefers the slice that unblocks the most others. A step of a slice that needs a later slice's contract waits for it; STATUS.md names those steps.
- `telemetry` may be pulled into wave 1 when the desktop clients move to staging, so their crash reports are not lost.
- Slices run in parallel. Each touches only its own paths. Shared registration points (router, composition root, navigation, locale bundles) take small, additive edits, committed with explicit paths.
- F4 is needed before a slice can be checked on https://shosai.tech; until then slices are verified locally.

## 5. Decisions the user must provide

| Needed by | Decision |
|---|---|
| F4 | The server for https://shosai.tech, SSH access for deployment, the DNS record, and the image registry (GHCR is proposed) |
| F4 | Whether deploys to staging run automatically after green CI and production deploys are manual with approval (proposed) |
| D4 | Which draft modules without a place in the target architecture are kept, merged or dropped — **decided 2026-10-01**, [FEATURE_MAP.md](FEATURE_MAP.md) section 7 |
| Slice map | The cut of the slices and its decisions SM-1…SM-15 — **decided 2026-10-13**, [SLICE_MAP.md](SLICE_MAP.md) §8.1 |
| billing | Sandbox credentials of the acquirers (TBank, CloudPayments, lava.top) for staging |
| agent, capture, meetings | API keys of AI providers for staging |
| M1, M2 | Read access to a copy of the production database and storage, and the cutover date |

Agents stop and ask when they reach one of these.

## 6. Launch lines

Paste one line as the first message of a new session. Replace `<name>` where shown.

| Package | Launch line |
|---|---|
| D1 | `Execute work package D1 from docs/plan/prompts/D1-contracts.md.` |
| D2 | `Execute work package D2 from docs/plan/prompts/D2-visual-parity.md.` |
| D3 | `Execute work package D3 from docs/plan/prompts/D3-data-mapping.md.` |
| D4 | `Execute work package D4 from docs/plan/prompts/D4-feature-map.md.` |
| F1 | `Execute work package F1 from docs/plan/prompts/F1-backend-foundation.md.` |
| F2 | `Execute work package F2 from docs/plan/prompts/F2-frontend-foundation.md.` |
| F3 | `Execute work package F3 from docs/plan/prompts/F3-local-environment.md.` |
| F4 | `Execute work package F4 from docs/plan/prompts/F4-delivery-staging.md.` |
| F5 | `Execute work package F5 from docs/plan/prompts/F5-observability.md.` |
| F6 | `Execute work package F6 from docs/plan/prompts/F6-platform-services.md.` |
| Slices | `Execute feature slice <name> from docs/plan/prompts/S-feature-slice.md.` — `<name>` is a slice of §3 Phase 2, for example `identity` |
| F1 audit | `Execute the F1 audit from docs/plan/prompts/F1-audit.md.` — one session before the backend path; the owner decides keep, fix or rebuild |
| Slice map | `Execute the slice map from docs/plan/prompts/SLICE-MAP.md.` — derived the slices from the cabinet and the philosophy; done 2026-10-13 |
| Backend, next step | `Execute the next backend step from docs/plan/prompts/BACKEND-next-step.md.` — the same line every session; the prompt picks the step: foundation per the F1 audit, then F6, then the slices of SLICE_MAP.md |
| M1 | `Execute work package M1 from docs/plan/prompts/M1-data-migration.md.` |
| M2 | `Execute work package M2 from docs/plan/prompts/M2-cutover.md.` |
