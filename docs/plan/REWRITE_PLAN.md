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
4. A large package spans several sessions: every feature slice, and F1, F2, F4, F5 and F6. The user starts it with the same launch line each time; the first session writes the package plan, each later session implements the next step of that plan ([prompts/README.md](prompts/README.md), "Session mode for multi-session packages").
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
| D2 | Visual baseline and parity harness | A route inventory, recorded API fixtures, and a Playwright harness that screenshots the draft and v2 frontends against the same fixtures and compares them. Since 2026-10-07 a record of the draft's screens and a coverage list, not a gate ([ADR 0022](../adr/0022-new-web-design-replaces-draft-parity.md)) |
| D3 | Data inventory and mapping | `docs/plan/DATA_MAPPING.md`: every draft table and bucket prefix mapped to its v2 place, including the home and company model |
| D4 | Feature map | `docs/plan/FEATURE_MAP.md`: every draft backend module and frontend feature mapped to a v2 slice; anything proposed for removal listed for the user's decision |

### Phase 1 — Foundation

| ID | Package | Output |
|---|---|---|
| F1 | Backend foundation | `backend/` project: `core/`, `composition/`, `entrypoints/` for `api`, `ws`, `workers`, `scheduler`; configuration; home-aware database sessions; Valkey, Redis cache and S3 clients; structured logging and telemetry; the error envelope; the model-facing-English test; import-linter contracts; test-database claiming; health endpoints |
| F2 | Frontend foundation | The cabinet in `frontend/`: the new web UI moved from Next.js to a Vite SPA without visual change — React Router, TanStack Query, `use-intl` with 16 locales, a data layer generated from the OpenAPI contract, the sample API removed, npm scripts required by CI ([ADR 0021](../adr/0021-public-site-on-nextjs-cabinet-on-vite.md)) |
| F3 | Local environment | `compose.dev.yaml`: PostgreSQL 18 with pgvector as **two databases standing in for the RU and EU homes**, Valkey, Redis cache, Qdrant, and later LiveKit; prepared test databases; one command to start and one to reset |
| F4 | Delivery to staging | Dockerfile (one image, four roles), production Compose, NGINX, TLS, image registry, `scripts/release.sh`, CI build and deploy to https://one.whisperer.one |
| F5 | Observability | OpenTelemetry Collector, Prometheus, Alertmanager, Loki, Tempo, Grafana configuration per target architecture §16, including the `alerting` domain |
| F6 | Platform services | The AI provider port that writes a cost row for every call, with spend control and the abuse guard; the email port; the periodic-job registry on `schedule_runs`. Added by D4 (decision FM-4) because most slices need them from their first step |

### Phase 2 — Feature slices

Each slice is a vertical piece: backend slice, frontend slice, tests, contract compatibility with D1, the slice's screens of the new web UI working on the API ([ADR 0022](../adr/0022-new-web-design-replaces-draft-parity.md)). The table below is the summary as D4 left it; the module-by-module map, the decisions FM-1…FM-5 (including the routes dropped for lack of any consumer) and the dependencies between slices are in [FEATURE_MAP.md](FEATURE_MAP.md).

| ID | Slice | Draft sources (backend) | Draft sources (frontend) |
|---|---|---|---|
| S01 | Identity: accounts, sign-in, sessions, devices, email verification, social login, token rotation, directory and home routing, data export and deletion | `features/identity`, `services/auth_service.py`, `refresh_session_service.py`, `desktop_auth_service.py`, `pending_registration.py`, `account_data.py`, `onboarding.py`, `api/auth.py`, `api/me.py`, `api/me_data.py`, `api/me_onboarding.py` | `auth`, `account`, `onboarding` |
| S02 | Organizations: companies, members, roles, seats, access policy, RLS, audit — **new in v2** | none; target architecture §7 | new screens in the draft's visual language |
| S03 | Billing: tariffs, subscriptions, credits, acquirers, auto-renewal, reconciliation, referral and affiliate, company invoices | `features/billing`, `services/payment`, `billing_service.py`, `auto_renew*`, `tariff_service.py`, `card_binding_service.py`, `affiliate_service.py`, `api/me_billing.py`, `api/billing_webhook.py`, `api/tariffs.py`, `api/admin/{tariffs,finance,payments,promocodes,affiliates}.py` | `billing`, `referral` |
| S04 | Meetings: sessions, transcripts, notes, folders and tags, templates, import, recordings, mind map, sharing, post-meeting pipeline | `features/meetings`, `api/sessions.py`, `api/me_sessions*`, `api/me_notes.py`, `api/me_templates.py`, `api/me_mindmap.py`, `api/me_meeting_org.py`, `services/session_manager.py`, `services/meeting_*`, `services/mindmap_*`, `notes_enhancer.py`, `web_meeting_result.py` | `meetings` |
| S05 | Realtime: live capture, voice assistant, call translation, subtitles, hotkeys | `features/realtime`, `features/subtitles`, `api/realtime*.py`, `api/websocket.py`, `api/ai/voice*.py`, `services/hotkey_service.py` | `hotkeys`; the live page of `meetings` |
| S06 | Rooms: LiveKit rooms, recording, per-participant track transcription, broadcasts, room whiteboard and AI panel | `services/livekit`, `room_*.py`, `api/me_rooms.py`, `api/rooms_public.py`, `api/livekit_webhooks.py`, `features/stream`, `features/whiteboard`, `features/meeting_assistant`, `web_meeting.py`, `web_stream.py` | `rooms`, `streams` |
| S07 | Knowledge and search: sources, indexing, Qdrant, keyword search, context graph; the legacy notes merged in (FM-2) | `features/knowledge`, `features/knowledge_engine`, `features/context_graph`, the legacy notes behind `services/rag_pipeline.py`, `api/me_search.py`, `services/global_search.py` | `knowledge`, `search` |
| S08 | Storage: files, presigned uploads, quotas, public links | `services/storage`, `api/me_storage.py`, `api/storage_public.py` | `storage` |
| S09 | Agent (Leo): chat, tools, skills, memory, personalization, proactive hints with Web Push, personal context, model catalogue and selection, prompts | `services/agent`, `services/skills`, model catalogue and registry in `services/llm`, `features/memory`, `features/personalization`, `features/proactive`, `api/ai/agent.py`, `api/ai/proxy.py`, `api/ai/dictate.py`, `api/me_models.py`, `api/me_skills.py`, `api/admin/{models,prompts,context}.py` | `leo`, `prompts`, `models`, `context` |
| S10 | MCP: Whisperer as an MCP server, MCP OAuth, MCP client | `api/mcp_*.py`, `api/me_mcp.py`, `services/mcp*`, `services/llm/mcp_*` | `mcp` |
| S11 | Errands: delayed Leo actions (periodic jobs moved to F6) | `features/errands` | — (panel inside `leo`) |
| S12 | Connectors and calendar: Nango, calendar sync, Jira, meeting-result push to Notion, Slack and CRM, OAuth integrations ([ADR 0002](../adr/0002-oauth-grants-outside-nango.md)) | `features/connectors`, `features/jira`, `services/calendar`, `services/oauth_providers`, `services/oauth*.py`, `services/integration*.py`, `api/calendar_*.py`, `api/me_calendar*.py`, `api/me_integrations.py`, `api/oauth_integrations.py` | `calendar` |
| S13 | Tracker | `api/me_tracker.py`, `services/tracker.py` | `tracker` |
| S14 | Analytics: product analytics, personal usage, satisfaction, client errors | `features/analytics`, `features/satisfaction`, `api/client_errors.py`, `api/admin/{analytics,client_errors}.py` | `analytics`, `product-analytics`, `satisfaction` |
| S15 | Administration and support: admin screens, users, dashboard, monitoring, tickets, newsletters | `api/admin/{users,dashboard,monitoring,tickets,broadcasts}.py`, `api/tickets.py`, `api/unsubscribe.py`, `services/ticket*_service.py`, `services/broadcast_service.py` | `platform-admin`, `support` |
| S16 | Hub, downloads and remaining modules: hubs (FM-1), client downloads, top-bar ticker | `features/hub`, `features/desktop`, `api/app_builds.py`, `api/admin/app_builds.py`, `api/ticker.py` | `hub`, `downloads` |
| S17 | Public site in `site/` on Next.js ([ADR 0021](../adr/0021-public-site-on-nextjs-cabinet-on-vite.md)): landing with its live demo, pricing, documentation, legal, help centre with its assistant, blog in 16 languages, public pages of shared links, SEO per [docs/seo/STRATEGY.md](../seo/STRATEGY.md) | `web_static.py`, `web_landing*.py`, `web_share.py`, `legal.py`, `features/demo`, `features/docs_assistant` (FM-1), `static/landing/`, `static/docs/` | — |

### Phase 3 — Data migration and cutover

| ID | Package | Output |
|---|---|---|
| M1 | Data migration | Tooling that moves the draft's production data into the v2 schema per D3, rehearsed on a copy, with verification of counts, invariants and money |
| M2 | Cutover | Runbook and rehearsal: maintenance window ≤ 30 min (nfr-12), `whisperer.one` switched to v2, rollback path, native clients verified against production |

## 4. Dependencies and parallelism

```text
D1 D2 D3 D4          (parallel, any time)
F3 ── F1 ── F6 ── S01 ── S02..S16   (slices in any order, in parallel)
      F2 ───────┘
F1 F2 F6 ── S17
F1 F2 ── F4 ── F5 (steps 1–5 of F4 and 1–6 of F5 need only F1)
all S + D3 ── M1 ── M2
```

- The user chose no feature order. The only fixed dependencies are technical:
  - F1, F2, F3 and F6 come before any slice;
  - S01 (identity) comes before the other slices, because every other slice needs an authenticated user;
  - D1 must exist before a slice can prove contract compatibility.
- Slices run in parallel. Each touches only its own paths. Shared registration points (router, composition root, navigation, locale bundles) take small, additive edits, committed with explicit paths.
- F4 is needed before a slice can be checked on https://one.whisperer.one; until then slices are verified locally.

## 5. Decisions the user must provide

| Needed by | Decision |
|---|---|
| F4 | The server for https://one.whisperer.one, SSH access for deployment, the DNS record, and the image registry (GHCR is proposed) |
| F4 | Whether deploys to staging run automatically after green CI and production deploys are manual with approval (proposed) |
| D4, S16 | Which draft modules without a place in the target architecture are kept, merged or dropped — **decided 2026-10-01**, [FEATURE_MAP.md](FEATURE_MAP.md) section 7 |
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
| F6 | `Execute work package F6 from docs/plan/prompts/F6-platform-services.md.` |
| S01–S17 | `Execute feature slice <ID> from docs/plan/prompts/S-feature-slice.md.` |
| M1 | `Execute work package M1 from docs/plan/prompts/M1-data-migration.md.` |
| M2 | `Execute work package M2 from docs/plan/prompts/M2-cutover.md.` |
