# Rewrite plan: draft → whisperer-v2

How the draft (`/root/whisperer`) is rewritten into the final version (`/root/whisperer-v2`). The rules are in [.claude/CLAUDE.md](../../.claude/CLAUDE.md) ("Rewrite from the draft" and everything else) and the architecture in [docs/design/ARCHITECTURE.md](../design/ARCHITECTURE.md). This plan does not repeat them; it orders the work.

- **Status of every work package:** [STATUS.md](STATUS.md).
- **Prompts to start an agent:** [prompts/](prompts/).

---

## 1. How the work runs

1. The user starts **one agent per work package, each in a new session**, opened in `/root/whisperer-v2` with read access to the draft:

   ```bash
   cd /root/whisperer-v2 && claude --add-dir /root/whisperer
   ```

2. The first message of the session is the package's launch line from [section 6](#6-launch-lines). It points the agent to its prompt file in [prompts/](prompts/).
3. The agent works, runs the checks, reports, and waits. It commits only after the user says «Принято».
4. A large package (most feature slices) spans several sessions. The first session writes the package plan; each later session implements the next step of that plan.
5. Several packages may run in parallel sessions when their dependencies are done ([section 4](#4-dependencies-and-parallelism)).

## 2. Facts every agent needs

| Fact | Value |
|---|---|
| Draft | `/root/whisperer` — read only. Production today runs the draft at `whisperer.one`. |
| Final version | `/root/whisperer-v2` — the only place that changes. |
| Test domain of v2 | **https://one.whisperer.one** — staging for v2. Separate from production: its own database, storage and secrets. |
| Hosting now | RU/EU data homes and EU Valkey are not available yet. Develop and test on local containers; the code stays home-aware (CLAUDE.md, "Hosting constraints now"). |
| Local tooling | uv 0.12.21, Python 3.14.7 (uv-managed), Node.js 26.10.0, npm 11, Docker 29.8 with Compose 5.5, ffmpeg. |
| Production data | Never read or write the draft's production database or storage. `backend/.env` of v2 holds production values of the draft — do not use them. |

### Done means, for every package

- The package's own definition of done (in its prompt) holds.
- Every check in CLAUDE.md passes: stage checks, tests, gates 100/100, mypy strict, CI green after push.
- Behaviour matches the draft; any difference is either demanded by CLAUDE.md or the target architecture, or approved by the user.
- [STATUS.md](STATUS.md) is updated in the same commit.
- Decisions that CLAUDE.md or the target architecture leave open are recorded as ADRs in `docs/adr/`, and the user has confirmed them.

## 3. Phases and work packages

### Phase 0 — Baselines from the draft

These packages read the draft and produce the references that every later package is checked against. They write no application code.

| ID | Package | Output |
|---|---|---|
| D1 | API and WebSocket contract baseline | `contracts/draft/`: the draft's OpenAPI, the WebSocket frame catalogue, and the list of endpoints and frames the shipped native clients use |
| D2 | Visual baseline and parity harness | A route inventory, recorded API fixtures, and a Playwright harness that screenshots the draft and v2 frontends against the same fixtures and compares them |
| D3 | Data inventory and mapping | `docs/plan/DATA_MAPPING.md`: every draft table and bucket prefix mapped to its v2 place, including the home and company model |
| D4 | Feature map | `docs/plan/FEATURE_MAP.md`: every draft backend module and frontend feature mapped to a v2 slice; anything proposed for removal listed for the user's decision |

### Phase 1 — Foundation

| ID | Package | Output |
|---|---|---|
| F1 | Backend foundation | `backend/` project: `core/`, `composition/`, `entrypoints/` for `api`, `ws`, `workers`, `scheduler`; configuration; home-aware database sessions; Valkey, Redis cache and S3 clients; structured logging and telemetry; the error envelope; the model-facing-English test; import-linter contracts; test-database claiming; health endpoints |
| F2 | Frontend foundation | `frontend/` project: Vite, React 19.3, TypeScript, Tailwind, router, data fetching, i18n with the draft's 16 locales, the draft's design tokens and app shell carried over for visual parity, npm scripts required by CI, the D2 harness wired in |
| F3 | Local environment | `compose.dev.yaml`: PostgreSQL 18 with pgvector as **two databases standing in for the RU and EU homes**, Valkey, Redis cache, Qdrant, and later LiveKit; prepared test databases; one command to start and one to reset |
| F4 | Delivery to staging | Dockerfile (one image, four roles), production Compose, NGINX, TLS, image registry, `scripts/release.sh`, CI build and deploy to https://one.whisperer.one |
| F5 | Observability | OpenTelemetry Collector, Prometheus, Alertmanager, Loki, Tempo, Grafana configuration per target architecture §16, including the `alerting` domain |

### Phase 2 — Feature slices

Each slice is a vertical piece: backend slice, frontend slice, tests, contract compatibility with D1, visual parity with D2 for its screens. The initial mapping below is refined by D4.

| ID | Slice | Draft sources (backend) | Draft sources (frontend) |
|---|---|---|---|
| S01 | Identity: accounts, sign-in, sessions, devices, email verification, social login, token rotation, directory and home routing, data export and deletion | `features/identity`, `services/auth*`, `oauth*`, `account_data.py`, `api/auth.py`, `api/me.py`, `api/me_data.py` | `auth`, `account`, `onboarding` |
| S02 | Organizations: companies, members, roles, seats, access policy, RLS, audit — **new in v2** | none; target architecture §7 | new screens in the draft's visual language |
| S03 | Billing: tariffs, subscriptions, credits, acquirers, auto-renewal, reconciliation, referral and affiliate, company invoices | `features/billing`, `services/payment`, `billing_service.py`, `auto_renew*`, `tariff_service.py`, `card_binding_service.py`, `affiliate_service.py`, `api/me_billing.py`, `api/billing_webhook.py`, `api/tariffs.py`, `api/me_affiliate.py` | `billing`, `referral` |
| S04 | Meetings: sessions, transcripts, notes, folders and tags, templates, import, recordings, mind map, sharing, post-meeting pipeline | `features/meetings`, `features/meeting_assistant`, `api/sessions.py`, `api/me_sessions*`, `api/me_notes.py`, `api/me_templates.py`, `api/me_mindmap.py`, `api/transcripts.py`, `api/me_recordings.py`, `services/mindmap_*`, `notes_enhancer.py` | `meetings` |
| S05 | Realtime: live capture, voice assistant, call translation, subtitles, broadcasts | `features/realtime`, `features/stream`, `features/subtitles`, `api/realtime*.py` | `streams`, `hotkeys` |
| S06 | Rooms: LiveKit rooms, recording, per-participant track transcription | `services/livekit`, `room_service.py`, `api/me_rooms.py`, `api/rooms_public.py`, `api/livekit_webhooks.py` | `rooms` |
| S07 | Knowledge and search: sources, indexing, Qdrant, keyword search, context graph | `features/knowledge`, `features/knowledge_engine`, `features/context_graph`, `api/kb.py`, `api/graph.py`, `api/me_search.py`, `services/global_search.py` | `knowledge`, `search`, `context` |
| S08 | Storage: files, presigned uploads, quotas, public links | `services/storage`, `api/me_storage.py`, `api/storage_public.py` | `storage` |
| S09 | Agent (Leo): chat, tools, skills, memory, personalization, proactive hints, model selection, prompts, provider port and cost | `services/agent`, `services/llm`, `services/skills`, `features/memory`, `features/personalization`, `features/proactive`, `features/docs_assistant`, `api/ai/`, `api/prompts.py`, `api/me_models.py`, `api/me_skills.py` | `leo`, `prompts`, `models` |
| S10 | MCP: Whisperer as an MCP server, MCP OAuth, MCP client | `api/mcp_*.py`, `api/me_mcp.py`, `services/mcp*` | `mcp` |
| S11 | Errands and scheduler: delayed Leo actions, periodic jobs | `features/errands`, `tasks/` | — |
| S12 | Connectors and calendar: Nango, calendar sync, Jira, CRM, Notion, OAuth integrations | `features/connectors`, `features/jira`, `services/calendar`, `api/calendar_*.py`, `api/me_calendar*.py`, `api/me_integrations.py`, `api/oauth_integrations.py` | `calendar` |
| S13 | Tracker | `api/me_tracker.py` and its services | `tracker` |
| S14 | Analytics: product analytics, satisfaction, client errors | `features/analytics`, `features/satisfaction`, `api/client_errors.py` | `analytics`, `product-analytics`, `satisfaction` |
| S15 | Administration and support: platform admin, model registry, tickets | `api/admin/`, `api/tickets.py`, `services/ticket_attachment_service.py` | `platform-admin`, `support` |
| S16 | Hub, downloads and remaining modules | `features/hub`, `features/whiteboard`, `features/demo`, `features/desktop`, `api/app_builds.py` | `hub`, `downloads` |
| S17 | Public site: landing, legal, help centre and blog in 16 languages, SEO per [docs/seo/STRATEGY.md](../seo/STRATEGY.md) | `web_landing*.py`, `web_meeting.py`, `legal.py`, `static/landing/` | — |

### Phase 3 — Data migration and cutover

| ID | Package | Output |
|---|---|---|
| M1 | Data migration | Tooling that moves the draft's production data into the v2 schema per D3, rehearsed on a copy, with verification of counts, invariants and money |
| M2 | Cutover | Runbook and rehearsal: maintenance window ≤ 30 min (nfr-12), `whisperer.one` switched to v2, rollback path, native clients verified against production |

## 4. Dependencies and parallelism

```text
D1 D2 D3 D4          (parallel, any time)
F3 ── F1 ── S01 ── S02..S17   (slices in any order, in parallel)
      F2 ─┘                  
F1 F2 ── F4 ── F5
all S + D3 ── M1 ── M2
```

- The user chose no feature order. The only fixed dependencies are technical:
  - F1, F2 and F3 come before any slice;
  - S01 (identity) comes before the other slices, because every other slice needs an authenticated user;
  - D1 and D2 must exist before a slice can prove contract compatibility and visual parity.
- Slices run in parallel. Each touches only its own paths. Shared registration points (router, composition root, navigation, locale bundles) take small, additive edits, committed with explicit paths.
- F4 is needed before a slice can be checked on https://one.whisperer.one; until then slices are verified locally.

## 5. Decisions the user must provide

| Needed by | Decision |
|---|---|
| F4 | The server for https://one.whisperer.one, SSH access for deployment, the DNS record, and the image registry (GHCR is proposed) |
| F4 | Whether deploys to staging run automatically after green CI and production deploys are manual with approval (proposed) |
| D4, S16 | Which draft modules without a place in the target architecture are kept, merged or dropped |
| S03 | Sandbox credentials of the acquirers (TBank, CloudPayments, lava.top) for staging |
| S09, S05 | API keys of AI providers for staging |
| M1, M2 | Read access to a copy of the production database and storage, and the cutover date |

Agents stop and ask when they reach one of these.

## 6. Launch lines

Paste one line as the first message of a new session. Replace `<ID>` where shown.

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
| S01–S17 | `Execute feature slice <ID> from docs/plan/prompts/S-feature-slice.md.` |
| M1 | `Execute work package M1 from docs/plan/prompts/M1-data-migration.md.` |
| M2 | `Execute work package M2 from docs/plan/prompts/M2-cutover.md.` |
