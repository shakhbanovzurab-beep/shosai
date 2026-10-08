# Feature map: draft → v2

Package D4 of the [rewrite plan](REWRITE_PLAN.md). Every capability of the draft has an owner in v2 here. The owner's keep, merge and drop decisions are in [section 7](#7-decisions-keep-merge-drop).

- **Built:** 2026-10-01 from the draft at commit `589917e84`.
- **Method:** HTTP and WebSocket routes, TaskIQ tasks, schedules, event consumers and tables were extracted from the draft's code by AST. Purposes come from module READMEs and docstrings. Slice-to-slice dependencies in [section 8](#8-cross-slice-dependencies) come from the draft's actual imports. Sizes count every line of `.py`, `.ts` and `.tsx` files; tests are excluded.
- **Neighbours:** exact endpoint and frame compatibility is D1's output (`contracts/draft/`), tables are D3's (`DATA_MAPPING.md`), screens are D2's. Sections 2.2 and 2.3 show D1's compatibility class of every route, taken from `contracts/draft/consumers.json`; D1 is authoritative on who uses a route.
- **Paths:** backend paths are relative to `/root/whisperer/backend/src/meetassist/`, frontend paths to `/root/whisperer/frontend/src/`.

**Legend for the v2 column:** `S01`–`S17` feature slices, `F1`–`F6` foundation packages, **replaced** — a target-architecture mechanism takes the place of the draft's one, `FM-n` — owner set by decision *n* in section 7.

---

## 1. Ownership by slice

| Slice | Domain (§5) | Draft backend | Draft frontend | Backend lines |
|---|---|---|---|---|
| S01 Identity | identity | `features/identity`; `api/auth.py`, `api/me.py` (profile, avatar, `GET /v1/me`), `api/me_data.py`, `api/me_onboarding.py`, `api/i18n.py`; services `auth_service`, `refresh_session_service`, `desktop_auth_service`, `pending_registration`, `captcha`, `account_data`, `onboarding`, `appearance_service`; `tasks/account_export.py`; `legal.py` | `auth`, `account`, `onboarding` | 6 500 |
| S02 Organizations | organizations | none — new in v2 | none — new screens | — |
| S03 Billing | billing | `features/billing`; `services/payment/`; services `billing_service`, `billing_receipts`, `tariff_service`, `pricing`, `subscription_stack`, `promo_service`, `referral_service`, `affiliate_service`, `auto_renew_service`, `auto_renew_reconciliation`, `auto_renew_status`, `card_binding_service`, `acquirer_subscription_service`; `config_billing.py`, `pricing_canon.py`; `api/me_billing.py`, `api/billing_webhook.py`, `api/tariffs.py`, `api/me.py` (`/referral`); admin `tariffs`, `finance`, `payments`, `promocodes`, `affiliates`; tasks `billing.*`, `billing.refresh_rates` | `billing`, `referral` | 12 200 |
| S04 Meetings | meetings | `features/meetings`; `api/sessions.py`, `api/me_sessions.py`, `api/me_sessions_import.py`, `api/me_notes.py`, `api/me_mindmap.py`, `api/me_meeting_org.py`, `api/me_templates.py`, `api/meeting_scope.py`; services `session_manager`, `notes`, `notes_enhancer`, `meeting_org`, `meeting_templates`, `meeting_export`, `meeting_archive`, `meeting_map_extractor`, `llm_mind_map_enricher`, `mindmap_*`, `import_jobs`, `diarized_transcript`; `tasks/extract_map.py`; `web_meeting_result.py` (`/r/{token}`) | `meetings` | 25 500 |
| S05 Realtime | realtime | `features/realtime`, `features/subtitles`; `api/realtime*.py`, `api/websocket.py`, `api/ai/voice_ws.py`, `api/ai/voice_translate.py`, `api/ai/voice_translate_ws.py`; `services/hotkey_service.py`, `api/me.py` (`/hotkeys`); `core/audio_frames.py`, `core/slot_pool.py`, `core/ws_frames.py` | `hotkeys`; the live page `/meetings/live` inside `meetings` | 12 600 |
| S06 Rooms | rooms | services `room_service`, `room_cleanup`, `room_recording_service`, `room_recording_transcription`; `services/livekit/`, `core/livekit/`; `api/me_rooms.py`, `api/rooms_public.py`, `api/livekit_webhooks.py`, `api/admin/livekit.py`; `features/stream`, `features/meeting_assistant`, `features/whiteboard` (FM-1); `web_meeting.py`, `web_stream.py`; task `rooms.idle_sweep` | `rooms`, `streams` | 9 500 |
| S07 Knowledge and search | knowledge | `features/knowledge`, `features/knowledge_engine`, `features/context_graph`; `services/global_search.py`, `api/me_search.py`; the legacy notes layer (FM-2) | `knowledge`, `search` | 18 000 |
| S08 Storage | — | `services/storage/`; `api/me_storage.py`, `api/storage_public.py`; `core/share_ticket.py`; tasks `storage.*` | `storage` | 2 400 |
| S09 Agent (Leo) | agent | `services/agent/`, `services/skills/`; `features/memory`, `features/personalization`, `features/proactive`; services `user_context_service`, `prompt_resolver`; model catalogue and registry in `services/llm/` (`catalog*`, `model_*`, `agent_*`, `ai_safety*`, `leo_identity`, `chat_attachments`, `chat_routing`, `file_extraction`, `prompt_composition`, `prompt_cache`, `free_fallback`); `api/ai/agent.py`, `api/ai/dictate.py`, `api/ai/proxy.py`, `api/me_models.py`, `api/me_skills.py`, `api/admin/models.py`, `api/admin/prompts.py`, `api/admin/context.py`; `tasks/sync_models.py`; the user event channel `WS /v1/ws/user` with `core/user_push.py` | `leo`, `prompts`, `models`, `context` | 31 300 |
| S10 MCP | — | `api/mcp_transport.py`, `api/mcp_oauth.py`, `api/me_mcp.py`; services `mcp`, `mcp_connect`, `mcp_connection_auth`, `mcp_oauth`, `mcp_scopes`, `mcp_stdio`; `services/llm/mcp_*`; `services/agent/mcp_tools.py`; task `mcp.health_check` | `mcp` | 4 500 |
| S11 Errands | errands | `features/errands` (Temporal **replaced** by `errands` rows run by the scheduler, §12) | none of its own; the errands panel lives in `leo` | 1 000 |
| S12 Connectors and calendar | connectors | `features/connectors` (Nango), `features/jira`; `services/calendar/`, `services/oauth_providers/`, services `oauth_service`, `oauth`, `integrations`, `integration_push`; `api/me_calendar.py`, `api/me_calendar_integrations.py`, `api/calendar_oauth.py`, `api/calendar_public.py`, `api/calendar_webhooks.py`, `api/me_integrations.py`, `api/oauth_integrations.py`; tasks `calendar.*` | `calendar`; `/settings/integrations` inside `meetings`; the connectors panel inside `leo` | 15 400 |
| S13 Tracker | — | `api/me_tracker.py`, `services/tracker.py` | `tracker` | 900 |
| S14 Analytics | analytics | `features/analytics`, `features/satisfaction`; `api/client_errors.py`, `api/admin/client_errors.py`, `api/admin/analytics.py`; services `client_error_service`, `analytics_buckets`, `analytics_validate`, `activity_calendar`; `api/me.py` (`/analytics*`) | `analytics`, `product-analytics`, `satisfaction` | 15 500 |
| S15 Administration and support | — | `api/admin/users.py`, `dashboard.py`, `monitoring.py`, `broadcasts.py`, `tickets.py`; `api/tickets.py`, `api/unsubscribe.py`; services `ticket_service`, `ticket_attachment_service`, `broadcast_service`, `monitoring_service`, `dashboard_metrics`; tasks `tickets.sweep_orphan_attachments`, `notifications.send_broadcast*` | `platform-admin`, `support` | 1 900 |
| S16 Hub, downloads and remaining modules | — | `features/hub` (FM-1), `features/desktop`; `api/app_builds.py`, `api/admin/app_builds.py`, `tasks/app_release.py`; the top-bar ticker: `api/ticker.py`, services `weather`, `holidays`, `stats` | `hub`, `downloads` | 5 300 |
| S17 Public site | — | `web_static.py` (public part), `web_landing_*.py`, `web_share.py`, `web_site_verification.py`; `services/help_docs.py`; `features/demo`, `features/docs_assistant` (FM-1); `backend/static/landing/`, `backend/static/docs/`, `docs/<lang>/` | none — static pages served by the backend | 6 500 |
| F1 Backend foundation | — | `core/` (except the parts named in other rows), `composition/`, `entrypoints/` (`temporal_worker.py` **replaced**), `main.py`, `config.py`, `utils/`, `i18n/`, `api/health.py`, `api/deps.py`, services `crypto`, `domain_events`; `tasks/outbox_relay.py` (relay to TaskIQ instead of NATS) | `app/`, `shared/` → F2 | 11 600 |
| F5 Observability | alerting | `features/alerting` (Telegram alerts on domain events); `deploy/prometheus`, `deploy/alertmanager`, `deploy/blackbox` | — | 500 |
| F6 Platform services (FM-4) | — | the AI provider port: provider clients in `services/llm/` (`openrouter_provider`, `_openai_compat`, `openai_asr`, `openai_realtime_asr`, `openai_realtime_translate`, `live_transcription_session`, `realtime_audio`, `gemini_live`, `deepgram_provider`, `embeddings`, `image_generate`, `vision_describe`, `router`), cost and spend control (`cost_tracker`, `spend_guard`, `spend_policy`, `voice_metering`, `premium_limits`, `live_capacity`, `provider_breaker`, `services/usage_tokens.py`), the abuse guard (`services/llm/abuse/`, `tasks/recompute_abuse.py`, `api/admin/abuse.py`), `core/llm/`, `api/ai/ws_metering.py`, `api/admin/costs.py`; email (`services/email/`, `tasks/send_email.py`); the periodic-job registry | — | 10 800 |

Draft models (`models/`, 4 300 lines, 69 files) follow the owner of each table; D3 maps every table. `schemas/` follows the owner of each schema.

---

## 2. Backend inventory

### 2.1 `features/` — 24 modules

| Module | Purpose | Entry points | Tables | Lines | v2 |
|---|---|---|---|---|---|
| `alerting` | Telegram alerts to the owner on registration, deletion, payment, support ticket, abuse flag | NATS consumers per event; no HTTP, no tables | — | 493 | F5 · alerting |
| `analytics` | Product analytics: event ingest, metric registry, funnels, cohorts, experiments, targets, journeys, feature health, anomaly insights, alerts, weekly digest | `POST /v1/analytics/collect`; 21 admin routes under `/v1/admin/{overview,metrics,funnels,cohorts,experiments,targets,alerts,insights,journeys,feature-health,reports}`; consumer `analytics__facts`; tasks `analytics.maintain_partitions`, `analytics.check_alerts`, `analytics.weekly_digest` | `analytics_events` (monthly partitions), device identity | 11 501 | S14 · analytics |
| `billing` | Tariffs, subscriptions, payments, promo codes, credits, payment routing, price consistency; the entitlements contract read by the whole platform | schedules `billing_reconcile_payments`, `billing_notify_expiring` | tables live in `models/` | 2 819 | S03 · billing |
| `connectors` | The user connects mail, calendar, drive, notes, trackers and CRM once; Leo reads and acts there through Nango. Providers: Gmail, Outlook, Google Drive, Dropbox, Yandex Disk, GitHub, GitLab, Notion, Slack, Confluence, Jira, HubSpot, Google Calendar | `/v1/connectors` (4 routes); task `connectors.refresh_health` | `connector_connections` | 5 983 | S12 · connectors |
| `context_graph` | Leo's personal context graph: people, projects, organisations, commitments, decisions, with sources in meetings | task `context_graph.project_meeting` | `pcg_entities`, `pcg_edges`, `pcg_facts` | 2 653 | S07 · knowledge |
| `demo` | The landing overlay answers for real: text, voice, screenshot, minutes and translation, no sign-up, free models only, per-IP caps | `POST /v1/demo/{ask,voice,minutes,translate}`; `WS /v1/ws/demo-translate` | none by design | 2 657 | S17 (FM-1) |
| `desktop` | Contract only: the "app build published" event | — | — | 43 | S16 |
| `docs_assistant` | "Ask" panel on help-centre pages; answers only from the documentation, in the page's language, with links | `POST /v1/docs/ask` | none by design | 1 433 | S17 (FM-1) |
| `errands` | Leo's delayed actions ("remind me in an hour", "send this next week"); execution on Temporal | `/v1/errands` (3); task `errands.repair`; Temporal workflow and worker process | `errands` | 1 021 | S11 · errands; Temporal **replaced** |
| `hub` | Workspace per client or project: meetings are assigned to it automatically, agreed actions go to its tracker board; Leo reads hubs | `/v1/hubs` (18) | `hubs`, `hub_meetings`, `hub_rules`, `hub_materials` | 4 460 | S16 (FM-1) |
| `identity` | Who calls (user JWT or device key); profile; social sign-in | `/v1/auth/social*` (9) | `user_identities` | 2 752 | S01 · identity |
| `jira` | Jira Cloud link of tracker projects: Atlassian OAuth, two-way issue sync, webhook, Atlassian personal-data reporting | `/v1/me/jira` (7), `/v1/jira/oauth`, `/v1/jira/webhook`; tasks `jira.sync_due`, `jira.report_accounts` | `jira_links`, `jira_issue_links` | 2 739 | S12 · connectors |
| `knowledge` | Knowledge base: documents and folders, quota, sources (OAuth via connectors, website crawl, Obsidian vault push), search. Answers come from Onyx | `/v1/knowledge/*` (16), `/v1/knowledge/vault` (3); consumers `source-connected`, `source-crawl`, `engine-document-indexed`; tasks `knowledge.purge_expired`, `knowledge.reconcile_usage` | `knowledge_space`, `knowledge_source`, `knowledge_document` | 6 357 | S07 · knowledge; Onyx **replaced** |
| `knowledge_engine` | Own engine on Qdrant: originals to S3, parsing, chunking, embeddings, hybrid retrieval, rerank, evaluation. Dormant without `QDRANT_URL`; shadow mode next to Onyx | no HTTP; 5 NATS consumers; tasks `knowledge_engine.sweep_stalled`, `knowledge_engine.reindex_stale` | `knowledge_document_version`, `knowledge_job`, `knowledge_chunk`, `knowledge_node`, `knowledge_retrieval_trace` | 8 121 | S07 — becomes the engine |
| `meeting_assistant` | AI panel inside a video room: questions about the meeting so far; room-pass authentication | `POST /v1/meeting-ai/ask` | — | 724 | S06 · rooms |
| `meetings` | Post-meeting pipeline (runs, stages, offline STT, pyannote diarization, polishing, semantics, impact on the workspace), canonical transcript, speakers, vector index of lines, retrieval and synthesis for Leo, public result page with comments, resumable audio upload | `/v1/me/sessions/{id}/…` (13: impact, audio upload parts), `/v1/me/sessions/{id}/share` (4), `/v1/meetings/shared/{token}` (3); tasks `meetings.run_stage`, `start_processing`, `recover`, `index_live`, `index_session`, `sweep_audio`, `close_idle_sessions`, `salvage_understanding` | `meeting_processing_runs`, `meeting_speakers`, `meeting_segment_embeddings`, `meeting_result_shares`, `meeting_share_comments`, `meeting_workspace_impacts` | 20 315 | S04 · meetings |
| `memory` | Leo's long-term memory between conversations | `/v1/memory` (5); tasks `memory.maintenance`, `memory.consolidation` | `memory_items` | 2 345 | S09 · agent |
| `personalization` | How Leo talks: style, adjustments, own instruction, occupation | `/v1/personalization` (2) | `leo_personalization` | 506 | S09 · agent |
| `proactive` | Leo speaks first: meeting soon, connection expired, errand due, important mail; PWA Web Push; the user event channel | `/v1/proactive/*` (15); `WS /v1/ws/user`; tasks `proactive.scan`, `scan_mail`, `purge_nudges`, `deliveries_sweep` | `proactive_settings`, `proactive_nudges`, `proactive_deliveries`, `proactive_mail_cursors`, `proactive_mail_watches`, `proactive_push_subscriptions` | 5 126 | S09 · agent |
| `realtime` | Server-side decision whether the assistant speaks up in a live meeting, language-independent | none; called by `api/realtime*.py` | — | 2 207 | S05 · realtime |
| `satisfaction` | "How satisfied are you" card every 20 days in all tariffs and 16 languages; admin results | `/v1/satisfaction/{prompt,answer,dismiss}`, `/v1/admin/satisfaction` (3) | survey table (created in a migration) | 2 435 | S14 · analytics |
| `stream` | Broadcasts: studio, stage, audience, knock and admission, chat, reactions, raised hands, moderation, bans; on LiveKit | `/v1/me/streams` (8), `/v1/streams/*` (24) | `streams`, `stream_members`, `stream_requests`, `stream_admissions`, `stream_chat_messages`, `stream_bans` | 5 416 | S06 · rooms (moved from S05) |
| `subtitles` | Live subtitles with translation in rooms; room-pass authentication | `/v1/subtitles/{recognize,translate,interpret}`; `WS /v1/subtitles/stream` | — | 1 609 | S05 · realtime |
| `whiteboard` | Whiteboard inside a video room (spec 078): save and load the scene | `GET`, `PUT /v1/whiteboard/scene` | `room_whiteboards` | 867 | S06 (FM-1) |

### 2.2 `api/` — top level

"D1 classes" counts the file's routes per compatibility class of `contracts/draft/consumers.json` (D1, in review): `native` and `external` must stay compatible, `web` changes together with the v2 frontend, `unused` is dropped except four routes (FM-5).

| File | Routes | Purpose | v2 | D1 classes |
|---|---|---|---|---|
| `auth.py` | 14 under `/v1/auth` | Register, verify email code, resend, forgot and reset password, login, refresh, logout, sessions list and revoke (kept although unused, FM-5), `me`, desktop code exchange and refresh | S01 | native 6 · web 6 · unused 2 |
| `me.py` | 9 under `/v1/me` | Profile, avatar, hotkeys, personal analytics, referral. Native clients read the profile through `GET /v1/auth/me` (`auth.py`), not `GET /v1/me`; their only call here is `/hotkeys` | S01, S05 (`/hotkeys`), S14 (`/analytics*`), S03 (`/referral`) | native 1 · web 8 |
| `me_data.py` | 4 under `/v1/me/data` | Export, "delete everything", account deletion | S01 | web 4 |
| `me_onboarding.py` | 6 under `/v1/me/onboarding` | Interactive tour progress | S01 | web 6 |
| `i18n.py` | `GET /v1/i18n/detect` | Language by IP for auto-detection | S01 | web 1 |
| `me_billing.py` | 14 under `/v1/me/billing` (+ dev router) | Checkout, renewal, cards, promo, credits | S03 | web 13 |
| `me_affiliate.py` | 3 under `/v1/me/affiliate` | Blogger affiliate programme | dropped (FM-5) | unused 3 |
| `billing_webhook.py` | 2 under `/v1/billing/webhook/{provider}` | Acquirer callbacks | S03 | external 2 |
| `tariffs.py` | `GET /v1/tariffs` | Public tariff list | S03 | web 1 |
| `sessions.py` | 6 under `/v1/sessions` | Legacy meeting CRUD and export | S04: `POST` and `PATCH` (native) only; the rest dropped (FM-5) | native 2 · unused 4 |
| `transcripts.py` | `GET /v1/sessions/{id}/transcripts`, `POST /v1/sync/batch` + 1 | Transcript read and offline batch sync | dropped (FM-5) | unused 3 |
| `me_sessions.py` | 16 under `/v1/me/sessions` | Meetings library: full view, map nodes, speakers, import, save to storage | S04 | native 6 · web 4 · unused 6 |
| `me_sessions_import.py` | helpers | Import validation | S04 | — |
| `me_notes.py` | 5 under `/v1/me/sessions/{id}/note*` | AI notes: draft, enhance, versions | S04 | native 3 · web 2 |
| `me_mindmap.py` | 1 | Mind map regeneration as a stream | S04 | web 1 |
| `me_meeting_org.py` | 10 under `/v1/me/{folders,tags,sessions}` | Folders and tags | S04 | web 10 |
| `me_templates.py` | 3 under `/v1/me/templates` | Note templates | S04 | web 3 |
| `meeting_scope.py` | — | Owner scoping of meetings (anti-IDOR) | S04 | — |
| `realtime.py`, `realtime_answer.py`, `realtime_context.py`, `realtime_limits.py`, `realtime_persist.py`, `realtime_prompts.py`, `realtime_prompt_texts.py`, `realtime_session.py`, `realtime_stream.py`, `realtime_vision.py` | `WS /v1/ws/realtime` | Live capture: audio in, `transcript`, `transcript.partial`, `answer.*`, vision from screenshots, minute accounting, resource limits | S05 | native 1 |
| `websocket.py` | `WS /v1/ws/sessions/{id}` | One meeting's events to all devices of the user | S05 | native 1 |
| `me_rooms.py` | 8 under `/v1/me/rooms` | Video rooms | S06 | web 5 · unused 3 |
| `rooms_public.py` | `/v1/rooms/join/{token}` | Guest join | S06 | web 1 |
| `me_recordings.py` | 2 under `/v1/me/recordings` | Room recordings | dropped (FM-5) | unused 2 |
| `livekit_webhooks.py` | `POST /v1/livekit/webhook` | Egress finished | S06 | external 1 |
| `me_search.py` | `GET /v1/me/search` | Global search across the cabinet | S07 | web 1 |
| `kb.py` | 8 under `/v1/kb` | Legacy notes: CRUD, import, reindex, search | dropped (FM-2, FM-5) | unused 8 |
| `graph.py` | 5 under `/v1/kb/graph` | Link graph of legacy notes | dropped (FM-2, FM-5) | unused 5 |
| `me_storage.py` | 14 under `/v1/me/storage` | Files and folders, upload, share, send to knowledge base | S08 | web 14 |
| `storage_public.py` | 5 under `/v1/storage/shared/{token}` | Public file and folder links | S08 | web 4 · unused 1 |
| `prompts.py` | 4 under `/v1/prompts` | Legacy prompt library and `execute` | dropped (FM-5) | unused 4 |
| `me_models.py` | 3 under `/v1/me/models` | User model per role | S09 | web 3 |
| `me_skills.py` | 7 under `/v1/me/skills` | Skills library (SKILL.md, skills.sh) | S09 | web 6 · unused 1 |
| `mcp_transport.py` | `POST`, `GET /mcp` | Whisperer as an MCP server (JSON-RPC, Streamable HTTP) | S10 | external 2 |
| `mcp_oauth.py` | 12: `/.well-known/oauth-*`, `/v1/mcp/oauth/*` | OAuth 2.1 of the MCP server | S10 | external 10 · unused 2 |
| `me_mcp.py` | 9 under `/v1/me/mcp` | MCP tokens, exposed resources, client connections | S10 | web 9 |
| `me_calendar.py` | 9 under `/v1/me/calendar` | Calendar events | S12 | web 7 · unused 2 |
| `me_calendar_integrations.py` | 7 under `/v1/me/calendar/integrations` | Google, Microsoft, CalDAV calendar connections | S12 | web 7 |
| `calendar_oauth.py` | 1 under `/v1/integrations/oauth/{provider}/callback` | Calendar OAuth callback | S12 | external 1 |
| `calendar_public.py` | `GET /v1/calendar/export.ics` | iCal subscription feed | S12 | external 1 |
| `calendar_webhooks.py` | 2 under `/v1/integrations/{google,microsoft}` | Calendar push notifications | S12 | external 2 |
| `me_integrations.py` | 6 under `/v1/me/integrations` | Meeting results pushed to Notion, Slack, HubSpot, Attio, Affinity, Zapier (bring your own credential) | S12 (FM-3) | web 6 |
| `oauth_integrations.py` | 4 under `/v1/integrations/oauth` | One-click OAuth for those integrations | S12 (FM-3) | external 4 |
| `me_tracker.py` | 21 under `/v1/me/tracker` | Projects, status columns, tasks, labels, Kanban | S13 | web 15 · unused 6 |
| `client_errors.py` | `POST /v1/client/errors`, `/v1/client/csp-report` | Client error intake | S14 | native 1 · external 1 |
| `tickets.py` | 9 under `/v1/me/tickets` | Support tickets of the user | S15 | web 9 |
| `unsubscribe.py` | 2 under `/v1/unsubscribe` | One-click unsubscribe from product news | S15 | external 2 |
| `app_builds.py` | 2 under `/v1/app/builds` | Public list and download of client builds | S16 | external 1 · web 1 |
| `ticker.py` | `GET /v1/ticker` | Top-bar ticker: weather, holiday, public stats | S16 | web 1 |
| `health.py` | `/health`, `/ready`, also under `/v1` | Liveness and readiness | F1 | web 1 · excluded 3 |
| `deps.py` | — | Dependency aliases | F1 | — |

### 2.3 `api/admin/` and `api/ai/`

| File | Routes | Purpose | v2 | D1 classes |
|---|---|---|---|---|
| `admin/users.py` | 7 | Users: list, card, role, block | S15 | web 7 |
| `admin/dashboard.py` | 1 | Users, revenue (MRR), usage summary | S15 | web 1 |
| `admin/monitoring.py` | 1 | Login events and errors | S15 | web 1 |
| `admin/tickets.py` | 8 | Support queue | S15 | web 8 |
| `admin/broadcasts.py` | 3 | Email newsletters | S15 | web 3 |
| `admin/tariffs.py`, `finance.py`, `payments.py`, `promocodes.py`, `affiliates.py` | 4, 4, 2, 4, 6 | Tariffs; transactions, refunds, CSV; acquirer switchboard; promo codes; affiliates and payouts | S03 | web 20 |
| `admin/models.py` | 12 | Model registry, defaults, role assignments, OpenRouter import | S09 | web 9 · unused 3 |
| `admin/prompts.py` | 9 | Platform prompts, global instructions, guardrail | S09 | web 8 · unused 1 |
| `admin/context.py` | 5 under `/v1/admin/context` | **The user's own** paid context (text, roles, files) despite the path; the path stays for compatibility | S09 | web 5 |
| `admin/costs.py` | 4 | Spend guard, kill switch, cost summary and timeline | F6 (FM-4); `guard` and `kill-switch` kept although unused (FM-5) | web 2 · unused 2 |
| `admin/abuse.py` | 3 | Abuse review queue | F6 (FM-4) | web 3 |
| `admin/analytics.py` | 6 | Usage drill-down from operational tables (spec 054) | S14 | web 4 · unused 2 |
| `admin/client_errors.py` | 2 | Client errors | S14 | web 2 |
| `admin/livekit.py` | 8 | SFU monitoring and room control | S06 | web 8 |
| `admin/storage.py` | 5 | Storage monitoring | dropped (FM-5) | unused 5 |
| `admin/sessions.py` | 4 | Meeting view, mind-map enrichment, deletion | dropped (FM-5) | unused 4 |
| `admin/app_builds.py` | 5 | Client build publishing | S16 | web 5 |
| `ai/agent.py` | 4 under `/v1/ai/agent` | Leo turn over the LangGraph graph; confirm action (`chat`, `act`) | S09 | web 4 |
| `ai/proxy.py` | 5 | `/v1/ai/chat/stream`, `/transcribe`, `/translate`, `/vision/analyze`, `/abuse/appeal` | S09: `/chat/stream` and `/vision/analyze` (native) only; the rest dropped (FM-5). `/transcribe` is reached only from dead code in both native clients | native 2 · unused 3 |
| `ai/dictate.py` | 1 | Dictation into chat via Gemini | S09 | web 1 |
| `ai/voice.py`, `ai/voice_ws.py` | 2 + `WS /v1/ws/voice` | Leo voice: Gemini Live tokens (dropped, FM-5) and WS proxy | S05 | web 1 · unused 2 |
| `ai/voice_translate.py`, `ai/voice_translate_ws.py` | 2 + `WS /v1/ws/voice-translate` | Simultaneous call translation | S05 | native 3 |
| `ai/ws_metering.py` | — | Spend metering of WS AI traffic | F6 (FM-4) | — |

### 2.4 `services/` — files not named in section 1

| File | Purpose | v2 |
|---|---|---|
| `file_watcher.py` | Watches a server folder of `.md` files and indexes them as global notes; started by `main.py` | FM-2 |
| `rag_pipeline.py`, `graph_builder.py`, `kb_scope.py` | Embeddings and hybrid search of legacy notes (pgvector), their link graph, read and write scoping | FM-2 |
| `help_docs.py` | Search over the public help centre | S17 |
| `monitoring_service.py` | Login and error events, antifraud aggregates | S15 |

Every other file in `services/` is named in a section 1 row.

### 2.5 Tasks and schedules

67 TaskIQ tasks (queues `critical`, `default`, `bulk`, `meeting`) and the scheduler's loops.

| v2 | Tasks | Schedules and scheduler loops |
|---|---|---|
| F1 | `messaging.relay_outbox`, `messaging.purge_outbox` | queue depth, stream trim, Redis health (15 s); outbox relay and purge |
| S01 | `account.export` | — |
| S03 | `billing.reconcile_payments`, `billing.notify_expiring`, `billing.auto_renew_sweep`, `billing.resolve_in_flight_charges`, `billing.reconcile_cards`, `billing.reconcile_acquirer_subscriptions`, `billing.refresh_rates` | `billing_reconcile_payments`, `billing_notify_expiring`; auto-renew loop; rates every 6 h; billing metrics |
| S04 | `meetings.run_stage`, `meetings.start_processing`, `meetings.recover`, `meetings.index_live`, `meetings.index_session`, `meetings.sweep_audio`, `meetings.close_idle_sessions`, `meetings.salvage_understanding`, `meetings.extract_map` | `meetings_recover`, `meetings_index_live`, `meetings_idle_sessions`, `meetings_salvage_understanding`, `meetings_sweep_audio` |
| S06 | `rooms.idle_sweep` | rooms cleanup (300 s) |
| S07 | `knowledge.purge_expired`, `knowledge.reconcile_usage`, `knowledge_engine.sweep_stalled`, `knowledge_engine.reindex_stale`, `context_graph.project_meeting`; legacy `knowledge.embed_chunks`, `knowledge.rebuild_graph` (FM-2) | `knowledge_purge_expired`, `knowledge_reconcile_usage`, `knowledge_engine_sweep_stalled`, `knowledge_engine_reindex_stale` |
| S08 | `storage.grace_sweep`, `storage.reconcile_usage` | storage maintenance (hourly, daily) |
| S09 | `memory.maintenance`, `memory.consolidation`, `proactive.scan`, `proactive.scan_mail`, `proactive.purge_nudges`, `proactive.deliveries_sweep`, `models.sync_openrouter`, `models.sync_speed`, `models.translate_descriptions` | `memory_maintenance`, `memory_consolidation`, `proactive_scan`, `proactive_scan_mail`, `proactive_purge_nudges`, `proactive_deliveries_sweep`; model sync |
| S10 | `mcp.health_check` | MCP health loop |
| S11 | `errands.repair` | `errands_repair` |
| S12 | `connectors.refresh_health`, `jira.sync_due`, `jira.report_accounts`, `calendar.send_invitations`, `calendar.send_due_reminders`, `calendar.send_cancellations`, `calendar.sync_integration`, `calendar.reconcile`, `calendar.push_event`, `calendar.push_delete`, `calendar.handle_notification`, `calendar.renew_watch_channels`, `calendar.poll_caldav`, `calendar.sweep_oauth_refresh`, `calendar.purge_notifications` | `connectors_refresh_health`, `jira_sync_due`, `jira_report_accounts`; calendar maintenance (300 s); calendar reminders (60 s) |
| S14 | `analytics.maintain_partitions`, `analytics.check_alerts`, `analytics.weekly_digest` | `analytics_partitions`, `analytics_alerts`, `analytics_digest` |
| S15 | `tickets.sweep_orphan_attachments`, `notifications.send_broadcast`, `notifications.send_broadcast_batch` | daily within storage maintenance |
| S16 | `app.notify_release` | — |
| F6 (FM-4) | `abuse.recompute_scores`, `notifications.send_email`, `notifications.send_bulk_email` | abuse recompute (300 s) |

In the draft, feature schedules are `ScheduleDefinition`s run by `entrypoints/scheduler_loops.py` under Redis leader locks. In v2 they are rows of `schedule_runs` (§12); F6 provides the periodic-job registry (FM-4), and each slice declares its own jobs.

### 2.6 Events

The draft publishes domain events through `outbox_messages` to NATS JetStream (streams `WHISPERER_EVENTS`, `WHISPERER_DLQ`); durable consumers: `alerting` (one per event type), `analytics__facts`, `knowledge__source-connected`, `knowledge__source-crawl`, `knowledge__engine-document-indexed`, and five `knowledge-engine__*`. In v2 the same events go through `outbox_messages` and one TaskIQ task per subscriber, deduplicated by `processed_events` (§12). NATS is **replaced**; no consumer is lost.

### 2.7 Public pages served by the backend

| Path | Module | v2 |
|---|---|---|
| `/`, `/{slug}/`, `/{lang}/…`, `/blog/…`, `/updates/…`, `/compare/…`, legal pages, 301 and 410 tables | `web_static.py`, `web_landing_allowlist.py`, `web_landing_redirects.py` | S17 |
| `/docs/…` help centre | `web_static.py` | S17 |
| `/llms.txt`, `/llms-full.txt`, `/llms/{name}`, `/robots.txt`, `/sitemap.xml`, `/sitemap.xsl`, `/indexnow-key.txt`, search-engine verification files | `web_static.py`, `web_site_verification.py` | S17 |
| `/fonts/…`, `/assets/…`, `/files/…`, `/img/…`, `/og.png`, `/og/…`, favicons, `/manifest.webmanifest`, `/email/{name}` | `web_landing_assets.py`, `web_static.py` | S17; PWA manifest and icons → F2 |
| `/app`, `/app/{path}` — the SPA | `web_static.py` | F2 and F4 (NGINX serves static assets in v2, §4.2) |
| `/meet/{token}`, `/rooms/join/{token}`, `/j/{token}` — link preview, then the SPA | `web_meeting.py` | S06 |
| `/live/{token}` | `web_stream.py` | S06 |
| `/r/{token}` | `web_meeting_result.py` | S04 |
| shared preview markup | `web_share.py` | S17, used by S04 and S06 |

### 2.8 Foundation code

| Draft | Content | v2 |
|---|---|---|
| `core/db`, `core/http`, `core/cache`, `core/security`, `core/web`, `core/observability`, `core/tasks`, `core/messaging` (outbox part), `core/module.py`, `core/process.py`, `core/rate_limit.py`, `core/redis_client.py`, `core/auth.py`, `core/jwt_utils.py`, `core/metrics.py`, `core/exceptions.py`, `core/security_headers.py`, `core/untrusted.py`, `core/channel_hub.py` | Database, HTTP clients, cache, security, middleware, telemetry, TaskIQ broker with dead letter and leases, outbox, feature registry, process roles, rate limits | F1 |
| `core/messaging/nats.py`, `streams.py`, `consumer.py` | NATS JetStream publisher and consumers | **replaced** by outbox + TaskIQ |
| `core/llm` | Provider base contracts | F6 (FM-4) |
| `core/user_push.py` | Publish to the user event channel; only `proactive` publishes | S09 |
| `core/livekit` | SFU client and room passes | S06 |
| `core/share_ticket.py` | Pass for password-protected shared folders | S08 |
| `core/audio_frames.py`, `core/slot_pool.py`, `core/ws_frames.py` | Audio framing, WS slots, frame helpers | S05 |
| `entrypoints/api.py`, `ws.py`, `worker.py`, `scheduler.py`, `scheduler_loops.py` | Four process roles | F1 |
| `entrypoints/temporal_worker.py` | Temporal worker | **replaced** (S11) |
| `composition/` | Providers, security wiring, metadata | F1 |

---

## 3. Frontend inventory

### 3.1 `features/` — 26 features

| Feature | Routes | Purpose | Backend it calls | Lines | v2 |
|---|---|---|---|---|---|
| `auth` | `/login`, `/register`, `/reset-password`, `/connect` (outside the shell) | Sign-in, registration, reset, desktop browser sign-in | `/auth/*`, `/auth/social`, `/client/errors` | 652 | S01 |
| `account` | `/cabinet/:tab?` | Profile, settings, time zone, theme, language, consents, export and deletion; the cabinet container | `/me/avatar`, `/me/data` | 110 | S01 |
| `onboarding` | shell slot | Tour, first-steps checklist, welcome, coach marks | `/me/onboarding` | 1 405 | S01 |
| `billing` | inside the cabinet | Tariffs, purchase, embedded acquirer form, promo, referral bonus, premium credits, auto-renewal | `/me`, `/me/billing`, `/tariffs` | 889 | S03 |
| `referral` | `/referral`, `/admin/affiliates` | Invitation link and counters; admin affiliates | `/me/referral`, `/admin/affiliates` | 175 | S03 |
| `meetings` | `/meetings`, `/meetings/live`, `/meetings/:id`, `/import`, `/templates`, `/settings/integrations`, `/r/:token` (outside the shell) | Library with folders, tags, search, import; meeting document (transcript, speakers, notes, map); live recording page; templates; integrations settings; public result | `/me/sessions`, `/me/folders`, `/me/tags`, `/me/templates`, `/me/integrations`, `/me/mcp`, `/meetings/shared`, `/meeting-ai` | 4 609 | S04 (`/meetings/live` uses S05; `/settings/integrations` uses S12) |
| `hotkeys` | `/hotkeys` | Keyboard shortcut map | `/me/hotkeys` | 180 | S05 |
| `rooms` | `/rooms/:id`, `/rooms/join/:invite` (outside the shell), `/admin/livekit` | Room: participant grid, dock, chat, reactions, hand, whiteboard, live subtitles with translation, recording, AI panel; admin SFU | `/me/rooms`, `/rooms/join`, `/rooms/knock`, `/me/sessions`, `/whiteboard/scene`, `/subtitles/*`, `/meeting-ai/ask`, `/admin/livekit` | 4 107 | S06 |
| `streams` | `/studio/:id`, `/live/:token` (outside the shell) | Broadcast studio and viewer page | `/me/streams`, `/streams/*` | 1 495 | S06 (moved from S05) |
| `knowledge` | `/knowledge-base` | Documents, search, quota, connected sources | `/knowledge/*` | 682 | S07 |
| `search` | shell slot | Command palette with global search | `/me/search` | 363 | S07 |
| `storage` | `/storage`, `/s/:token` (outside the shell) | Folders, uploads, viewer, moves, public links with password and expiry | `/me/storage`, `/storage/shared` | 1 383 | S08 |
| `leo` | shell slot | Chat widget with actions and confirmations, attachments, images, voice and dictation; Leo tab in the cabinet: memory, personalization, proactive settings, connectors, errands, skills | `/ai/agent`, `/ai/dictate`, `/memory*`, `/personalization`, `/proactive/*`, `/connectors*`, `/errands*`, `/me/skills`, `/me/search`, `/admin/prompts`; `WS /v1/ws/user` | 4 324 | S09 (calls S11 and S12 APIs) |
| `prompts` | `/prompts`, `/prompts/:id` | Prompt library, import, global instructions, guardrail; editor with versions | `/prompts`, `/admin/prompts` | 387 | S09 |
| `models` | `/models`, `/admin/ai-models` | Model catalogue, scorecard, model per role; admin registry | `/me/models`, `/admin/models` | 342 | S09 |
| `context` | `/context` | "About me", roles and files Leo mixes in (paid) | `/admin/context` | 415 | S09 |
| `mcp` | `/settings/mcp`, `/connect/mcp` (outside the shell) | Own MCP server, connecting external servers, consent screen | `/me/mcp`, `/mcp/oauth` | 291 | S10 |
| `calendar` | `/calendar`, `/rooms` | Day, week, month views; four event types; reminders; external calendars; rooms list | `/me/calendar` | 848 | S12 (the `/rooms` list calls S06) |
| `tracker` | `/tracker`, `/tracker/:projectId` | Projects, Kanban board, labels, priorities, Jira link | `/me/tracker`, `/me/jira` | 1 130 | S13 (Jira link calls S12) |
| `analytics` | `/analytics` | Personal usage by day, week, month; activity calendar | `/me/analytics` | 370 | S14 |
| `product-analytics` | `/admin/analytics` | Executive overview, funnels, cohorts, feature health, targets, alerts, metric dictionary and graph | `/admin/{overview,metrics,funnels,cohorts,…}` | 615 | S14 |
| `satisfaction` | shell slot, `/admin/satisfaction` | Survey card; admin results | `/satisfaction/*`, `/admin/satisfaction` | 362 | S14 |
| `platform-admin` | `/dashboard`, `/costs`, `/admin/{users,tariffs,finance,security,monitoring,abuse,client-errors,prompts}` | Internal administration | `/admin/{dashboard,users,tariffs,promocodes,finance,payments,monitoring,abuse,client-errors,prompts}` | 583 | S15 (screens over the admin APIs of S03, S14, F6) |
| `support` | `/support`, `/admin/support` | Tickets with attachments, FAQ; admin queue and newsletters | `/me/tickets`, `/admin/tickets`, `/admin/broadcasts` | 685 | S15 |
| `hub` | `/hub`, `/hub/:hubId` | Hubs list and hub page | `/hubs*`, `/me/tracker` | 850 | S16 (FM-1) |
| `downloads` | `/download`, `/admin/app` | Published client builds; admin publishing | `/app/builds`, `/admin/app` | 168 | S16 |

### 3.2 `app/` and `shared/`

| Path | Content | v2 |
|---|---|---|
| `app/` — router, registry, shell (`AppShell`, `Sidebar`, `TopBar`, `ConnectionOverlay`, nav groups), analytics bootstrap, i18n bootstrap | App frame | F2 |
| `shared/api`, `auth`, `hooks`, `i18n`, `lib`, `navigation`, `pwa`, `query`, `stores`, `styles`, `theme`, `types`, `ui` | Shared infrastructure, design tokens, UI kit | F2; a module only one slice imports moves into that slice (F2-D4, [F2 plan](packages/F2-frontend-foundation.md) §3.9) |
| `shared/markdown` | Markdown, code highlight, math, Mermaid | F2 hosts it in `core/`; built by the first slice that needs it (F2-D4) |
| `shared/analytics` | Event SDK, GA4, Yandex Metrika goals | F2 hosts it; the event catalogue follows S14 |
| `shared/entitlements` | Premium banner, subscription state | F2 hosts it; reads S03's contract |
| `shared/uploads` | Upload centre and queue | F2 hosts it in `core/`; built by the first slice that needs it (F2-D4); uses S08's upload contract |
| `locales/` | 16 locales | F2 |

---

## 4. Specifications carried over

Draft specifications in `/root/whisperer/specs/`. The owner carries the behaviour, not the draft's implementation.

| v2 | Specifications |
|---|---|
| F1 | 009 production gate (with S03 for billing dev mode), 010 proxy trust and rate limits, 013 health and supervised loops (with F5), 017 database health, 018 backend CI, 020 scheduler scale-out (becomes one scheduler process and `schedule_runs`), 035 no `create_all` in production |
| F2 | 005 react-doctor 100, 007 platform i18n (with S17 for SEO), 032 markdown XSS, 033 code splitting, 036 i18n keys, 077 frontend foundation decisions, 084 font roles |
| S01 | 001 email code, 022 refresh-token rotation, 031 device key is not admin, 082 appearance |
| S03 | 019 referral zero-cost guard, 024 webhook idempotency, 025 and 030 affiliate payout locks, 051 single price source, 060 auto-renewal, 070 premium weekly limits |
| S04 | 029 Granola-level meetings, 034 mind-map editor, 037 folders and tags, 039 AI notes, 042 import and transcription, 043 templates, 044 meeting AI settings, 046 meeting model selector |
| S05 | 015 WS resource limits, 040 web live recording, 058 voice (Gemini Live), 068 voice translation, 079 subtitles part |
| S06 | 066 LiveKit rooms, 067 room recording, 078 whiteboard, 079 stream part, 080 stream as an entity |
| S07 | 014 cross-tenant scoping (GRAPH-01; WS-03 → S05), 027 pgvector ANN index (superseded by Qdrant; see CLAUDE.md "Undecided", the role of pgvector) |
| S09 | 003 chat widget, 004 per-user prompts and guardrail, 053 model registry, 056 chat attachments, 057 admin model control, 073 unified agent, 074 LangGraph agent |
| F6 (FM-4) | 002 OpenRouter migration, 008 and 016 abuse guard, 012 spend metering, 028 hot-path quota and warm router |
| S10 | 045 meeting MCP, 049 MCP client |
| S12 | 047 meeting integrations, 048 CRM integrations, 050 Notion OAuth, 061, 062, 064 calendar, 072 calendar video meetings (with S06) |
| S13 | 063 tracker |
| S14 | 054 admin analytics drill-down, 055 GA4 funnel |
| S15 | 052 admin security section |
| S17 | 041 IndexNow |
| none | 021 and 069 (native clients, out of scope), 079 macOS teleprompter (native client), 059 moneta.ru checkout (removed in the draft; only legacy transactions remain, D3), 083 text size (withdrawn by the owner) |

Draft documents in `/root/whisperer/docs/` follow the same owners: `analytics/` → S14, `leo/` and the LEO reports → S09, `MEETING_INTELLIGENCE_*` → S04, `KNOWLEDGE_ENGINE_*` → S07, `REALTIME_*` and `AUDIO_ONBOARDING.md` → S05, `SPEND_CONTROL.md` → F6, `OAUTH-INTEGRATIONS.md` → S12, `OBSIDIAN-*` → S07 (vault push), `MCP-STDIO-DESKTOP.md` → S10, `seo/`, `SEO.md` and the 16 language folders → S17, `DATA_OWNERSHIP.md` and `DB-MIGRATION-TIMEWEB.md` → D3, `DEPLOY.md` and `infrastructure/` → F4. `ONYX-DEPLOY-PROMPT.md` has no successor (Onyx replaced). `x-growth/` and `content-prompts/` are marketing material outside the rewrite.

---

## 5. Infrastructure

| Draft | Role | v2 |
|---|---|---|
| `docker-compose.prod.yml`: `api`, `api-next`, `ws`, `ws-next`, `scheduler`, `worker-critical`, `worker-default`, `worker-bulk`, `worker-meeting` | Four roles, blue/green pairs | F4 |
| `redis-cache`, `qdrant` | Cache, vector index | F3, F4 |
| `nginx`, `certbot`, `nginx-exporter` | Edge and TLS | F4; exporter → F5 |
| `prometheus`, `alertmanager`, `blackbox` | Metrics and alerts | F5 (plus Loki, Tempo, Collector, Grafana) |
| `nats-0..2`, `deploy/nats` | Event bus | **replaced** by outbox + TaskIQ |
| `docker-compose.temporal.yml` (`temporal-db`, `temporal`, `temporal-ui`, `temporal-worker`), `deploy/temporal` | Errand execution | **replaced** by `errands` rows and the scheduler |
| `docker-compose.nango.yml` | Nango | F3, F4 (one per home), S12 |
| `deploy/livekit` | LiveKit, egress, coturn | F3, F4, S06 |
| Onyx (external service, not in Compose) | Knowledge base search | **replaced** by Qdrant (S07) |
| `.github/workflows/backend-ci.yml`, `nginx-ci.yml`, `pins-ci.yml`, `react-doctor.yml` | CI | already covered by v2 `ci.yml`; NGINX checks → F4 |
| `.github/workflows/windows-client-ci.yml` | Native client CI | out of scope |
| `scripts/release.sh`, `check_pins.py` | Release, pinned versions | F4 |
| `scripts/i18n`, `ga4_weekly_report.py`, `x_scout.py` | Locale tooling; marketing reports | F2; outside the rewrite |

---

## 6. Gaps

### 6.1 In the draft, not mentioned by the target architecture

All of these keep an owner; none conflicts with the target architecture. They follow its rules like any other slice.

| Capability | Owner |
|---|---|
| Tracker and its Jira link | S13, S12 |
| Calendar with two-way sync (Google, Microsoft, CalDAV), iCal feed, invitations and reminders | S12 |
| Files, folders, public links with password and expiry | S08 |
| MCP server and MCP client, including STDIO for desktop | S10 |
| Meeting result push to Notion, Slack, HubSpot, Attio, Affinity, Zapier | S12 |
| Knowledge sources: website crawl, Obsidian vault push (`/v1/knowledge/vault`, used by the Obsidian plugin) | S07 |
| Leo: memory, personalization, proactive hints with mail scanning, PWA Web Push, skills library, image generation, web search, dictation | S09 |
| Personal context for Leo (`/context`) | S09 |
| Prompt library and platform guardrail | S09 |
| Anti-abuse detector with dynamic model routing | F6 (FM-4) |
| Referral and affiliate programmes (the affiliate's own API is unused and dropped, FM-5; the admin side stays), promo codes, premium credits | S03 |
| Satisfaction survey | S14 |
| Onboarding tour, hotkeys, interface font | S01, S05, S01 |
| Support tickets and email newsletters with unsubscribe | S15 |
| Top-bar ticker (weather, holiday, public stats) | S16 |
| Client downloads and release notifications | S16 |
| Hubs, room whiteboard, landing demo, help-centre assistant | FM-1 |
| Broadcast studio with audience, chat and moderation (fr-10 says "broadcasts") | S06 |

### 6.2 Required by the target architecture, absent or partial in the draft

| Requirement | Draft state | Owner |
|---|---|---|
| Companies, memberships, roles, seats, invitations, domain join (fr-12, §7) | absent — no organisation, membership or seat in any table | S02 |
| One access policy, `resource_grants`, access levels on meetings, notes, folders, knowledge collections (fr-13, §7) | absent — every check compares the owner `user_id` | S02; every slice with company resources (S04, S07, S08 for folders) adopts it |
| RLS on company-scoped tables (§7) | absent | F1 groundwork, S02 policies |
| Audit log `org_audit_events` (nfr-17, inv-17) | absent | S02 |
| Company billing per seat, invoices, closing documents, bank-statement reconciliation (fr-15) | absent | S03 |
| Two data homes, directory by `HMAC(email)`, home in the token, account transfer saga (fr-7, §6) | absent — one database | F1 (home-aware sessions), F3, S01 (directory, transfer) |
| Work account separate from personal account (§6) | absent | S01, S02 |
| Per-participant transcription of rooms through LiveKit track egress to the WS gateway (fr-16, §11.2) | absent — the draft records the whole room and diarizes it after the meeting (Deepgram, pyannote) | S06 (egress), S05 (ingest) |
| Transcript line: server `seq`, durable Redis queue before the frame is sent, 500-ms batches to the home DB (inv-6, §8.1) | partial — the server assigns `seq`; lines are written directly to the database from the WS process | S05, S04 |
| `POST /v1/me/sessions/{id}/end` → 202 `{run_id}`, `GET /v1/me/runs/{run_id}` (§10) | absent — processing starts from the WS end and from sweeps | S04 (additive; draft paths stay) |
| Presigned multipart uploads `POST /v1/me/uploads` (§10) | partial — storage and meeting audio parts go through the API process; downloads are presigned | S08 (additive; draft paths stay) |
| `PUT /v1/{resource}/{id}/access` (§10) | absent | S02 with S04, S07, S08 |
| Every model call through one provider port that writes the cost row with an effect key (§14.4, inv-9) | partial — `cost_tracker` and `spend_guard` exist, but provider clients are created in many places (`features/meetings/infrastructure/diarizer_pyannote.py`, `services/llm/deepgram_provider.py`, `gemini_live.py`, `openai_*`) | F6 (FM-4) |
| WS: `hello` with protocol version, `transcription.busy`, `server.shutdown`, 1013 when full (§10) | partial — `hello` and `retry_later` exist; 1013 on drain exists | S05 |
| Outbox → TaskIQ, `processed_events` per consumer (§12) | partial — outbox exists, relay goes to NATS | F1 |
| `schedule_runs`; scheduler walks both homes (§8.1, §12) | absent — Redis leader locks | F6 |
| Deletion registry covering every table, S3 prefix and external grant (§14.7) | partial — `services/account_data.py` | S01, each slice registers its tables |
| Cursor pagination with a maximum page size (§10) | to be checked by D1 | every slice |
| Loki, Tempo, OpenTelemetry Collector, Grafana (§16) | absent — Prometheus, Alertmanager, blackbox only | F5 |
| Cross-border consent for Russian users and companies (nfr-14) | to be checked | S01 (personal consent), S02 (company contract) |

### 6.3 Draft mechanisms the target architecture replaces

| Draft | v2 | User-visible effect |
|---|---|---|
| NATS JetStream for domain events | Outbox + one TaskIQ task per subscriber (§12) | none |
| Temporal for errands | `errands` rows run by the scheduler (§12, §19) | none |
| Onyx for knowledge search | Qdrant with PostgreSQL keyword fallback (§4.2) | none expected. **Risk for M1:** documents uploaded through the draft's knowledge form went straight to Onyx and were not stored by the draft (`knowledge_engine/application/intake.py`); D3 must find whether originals exist for every document |
| Uploads proxied through the API process | Presigned multipart to the bucket (§10, §19) | none; draft paths stay for native clients |
| One database | Two homes and the directory | none for a user; transfer between homes is new |

---

## 7. Decisions: keep, merge, drop

All decisions were taken by the user on 2026-10-01. In each case the user chose the proposal.

| ID | Draft module | Decision | Alternative not taken, and its effect | Decided |
|---|---|---|---|---|
| FM-1a | `features/demo` (+ `WS /v1/ws/demo-translate`) | **Keep**, in S17. Calls go through the provider port with a platform cost account and per-IP caps; nothing is stored | Drop: the landing overlay stops answering and would have to show a recording — a visible change on the landing | 2026-10-01 |
| FM-1b | `features/docs_assistant` | **Keep**, in S17 | Drop: the "Ask" panel disappears from help-centre pages | 2026-10-01 |
| FM-1c | `features/whiteboard` | **Keep**, in S06 | Drop: the whiteboard button disappears from the room dock | 2026-10-01 |
| FM-1d | `features/hub` | **Keep**, in S16. Its access model inside companies (hubs are not among the shareable resources of §7) is settled in the S16 plan, with the owner | Drop: the "Hubs" item in the Work group disappears; meetings are no longer assigned to a hub and actions no longer reach its tracker board; Leo loses the hub tools | 2026-10-01 |
| FM-2 | Legacy notes: `api/kb.py`, `api/graph.py`, `services/rag_pipeline.py`, `graph_builder.py`, `kb_scope.py`, `file_watcher.py`, tasks `knowledge.embed_chunks`, `knowledge.rebuild_graph`, tables `notes`, `chunks`, `embeddings`, `kb_link_edges` | **Merge** into S07: notes become one source of the knowledge base on Qdrant; Leo keeps saving notes and live answers keep finding them. `/v1/kb*`, the notes link graph and the server-folder watcher are dropped — no screen and no shipped client calls them. D3 maps the notes into the knowledge base; S07 decides what happens to the admin-global notes (`user_id` empty) | Keep as is: a second search store with its own API. Drop entirely: Leo can no longer save notes, live answers lose this source, existing notes are lost | 2026-10-01 |
| FM-3 | OAuth outside Nango: calendars (`services/oauth_providers/google.py`, `microsoft.py`, `oauth_service.py`; CalDAV), Jira (`oauth_providers/jira.py`), meeting-result push (`services/oauth.py`) | **Keep the split**: Nango for Leo's connectors and knowledge sources; calendars, Jira and meeting push keep their own OAuth with tokens encrypted in the user's home; the deletion registry revokes every grant, inside and outside Nango. Recorded in [ADR 0002](../adr/0002-oauth-grants-outside-nango.md) | Everything in Nango: one grant registry, but M1 imports every token into Nango or users reconnect calendars, Jira and integrations | 2026-10-01 |
| FM-4 | Shared platform capabilities: the provider port with cost rows, spend guard and abuse guard; email; the periodic-job registry | **New foundation package F6 Platform services** ([prompt](prompts/F6-platform-services.md)), after F1 and before S01. The draft imports the provider port from 10 slices and email from 7 | Inside F1: F1 grows and finishes later. With the first consumer (S09, S01, S11): S04, S05, S06, S07, S14 and S17 would wait for S09's first step, and S03, S08, S12, S14, S15 and S16 for S01's email | 2026-10-01 |
| FM-5 | The 93 routes D1 classifies `unused`: no live consumer in the web frontend, the working native clients (macOS 1.4.5, Windows 1.4.5) or external parties. Seven of them are called only from dead code, which the owner decided on 2026-10-01 is not carried over | **Drop**, except four that the target architecture or operations need: `GET /v1/auth/sessions` and `DELETE /v1/auth/sessions/{session_id}` (S01: list and revoke one's own sessions, fr-6 devices), `GET /v1/admin/costs/guard` and `POST /v1/admin/costs/kill-switch` (F6: the operator's spend kill switch). Nothing visible changes: nobody calls these routes. The capability behind a dropped route stays where a screen or Leo uses it; only the HTTP route goes. Section 7.1 lists the routes | Keep all: more code and attack surface for no visible use. Drop all: the operator loses the kill switch over HTTP and users have no API for their device sessions | 2026-10-01 |

Not put to a decision, because the target architecture already decides them: NATS, Temporal and Onyx are replaced (section 6.3). If the owner wants any of them kept, the target architecture changes first.

### 7.1 Routes dropped by FM-5

89 routes, from D1's classification of 2026-10-01 (`contracts/draft/consumers.json`, in review). If D1 reclassifies a route before its slice is planned, the slice follows D1: a route that turns out to have a consumer is kept.

| Draft file | Routes |
|---|---|
| `api/admin/analytics.py` | `GET /v1/admin/analytics/models`, `GET /v1/admin/analytics/users` |
| `api/admin/models.py` | `GET /v1/admin/models/configs`, `GET /v1/admin/models/roles`, `PUT /v1/admin/models/roles/{role}` |
| `api/admin/prompts.py` | `POST /v1/admin/prompts/{prompt_id}/duplicate` |
| `api/admin/sessions.py` | `GET /v1/admin/sessions`, `DELETE /v1/admin/sessions/{session_id}`, `POST /v1/admin/sessions/{session_id}/enrich-mindmap`, `GET /v1/admin/sessions/{session_id}/full` |
| `api/admin/storage.py` | `GET /v1/admin/storage/health`, `GET /v1/admin/storage/overview`, `GET /v1/admin/storage/users`, `GET /v1/admin/storage/users/{user_id}`, `PATCH /v1/admin/storage/users/{user_id}/quota` |
| `api/ai/proxy.py` | `POST /v1/ai/abuse/appeal`, `POST /v1/ai/transcribe`, `POST /v1/ai/translate` |
| `api/ai/voice.py` | `POST /v1/ai/voice/token`, `POST /v1/ai/voice/usage` |
| `api/graph.py` | `GET /v1/kb/graph`, `GET /v1/kb/graph/centrality`, `GET /v1/kb/graph/export`, `GET /v1/kb/graph/neighbors`, `GET /v1/kb/graph/shortest-path` |
| `api/kb.py` | `POST /v1/kb/import`, `GET /v1/kb/notes`, `POST /v1/kb/notes`, `DELETE /v1/kb/notes/{note_id}`, `GET /v1/kb/notes/{note_id}`, `PUT /v1/kb/notes/{note_id}`, `POST /v1/kb/reindex`, `POST /v1/kb/search` |
| `api/mcp_oauth.py` | `GET /v1/mcp/oauth/clients`, `DELETE /v1/mcp/oauth/clients/{client_pk}` |
| `api/me_affiliate.py` | `GET /v1/me/affiliate`, `POST /v1/me/affiliate/apply`, `POST /v1/me/affiliate/payout` |
| `api/me_calendar.py` | `GET /v1/me/calendar/events/{event_id}`, `POST /v1/me/calendar/events/{event_id}/join` |
| `api/me_recordings.py` | `GET /v1/me/recordings`, `DELETE /v1/me/recordings/{recording_id}` |
| `api/me_rooms.py` | `GET /v1/me/rooms`, `POST /v1/me/rooms`, `POST /v1/me/rooms/{room_id}/close` |
| `api/me_sessions.py` | `POST /v1/me/sessions/{session_id}/enrich-mindmap`, `POST /v1/me/sessions/{session_id}/map-nodes`, `DELETE /v1/me/sessions/{session_id}/map-nodes/{node_id}`, `PATCH /v1/me/sessions/{session_id}/map-nodes/{node_id}`, `POST /v1/me/sessions/{session_id}/map-nodes/{node_id}/move`, `POST /v1/me/sessions/{session_id}/regenerate-mindmap` |
| `api/me_skills.py` | `GET /v1/me/skills/{skill_id}` |
| `api/me_tracker.py` | `DELETE /v1/me/tracker/labels/{label_id}`, `PATCH /v1/me/tracker/labels/{label_id}`, `GET /v1/me/tracker/projects/{project_id}`, `GET /v1/me/tracker/projects/{project_id}/labels`, `GET /v1/me/tracker/projects/{project_id}/tasks`, `GET /v1/me/tracker/tasks/{task_id}` |
| `api/prompts.py` | `GET /v1/prompts`, `POST /v1/prompts`, `GET /v1/prompts/{prompt_id}`, `POST /v1/prompts/{prompt_id}/execute` |
| `api/sessions.py` | `GET /v1/sessions`, `DELETE /v1/sessions/{session_id}`, `GET /v1/sessions/{session_id}`, `GET /v1/sessions/{session_id}/export` |
| `api/storage_public.py` | `GET /v1/storage/shared/{token}` |
| `api/transcripts.py` | `GET /v1/sessions/{session_id}/transcripts`, `POST /v1/sessions/{session_id}/transcripts`, `POST /v1/sync/batch` |
| `features/analytics/channels/admin/experiments.py` | `GET /v1/admin/experiments`, `GET /v1/admin/experiments/{slug}/result` |
| `features/analytics/channels/admin/journeys.py` | `POST /v1/admin/journeys/next-steps`, `POST /v1/admin/journeys/timeline` |
| `features/analytics/channels/admin/reports.py` | `GET /v1/admin/insights/digest`, `POST /v1/admin/metrics/export` |
| `features/analytics/channels/admin/targets.py` | `GET /v1/admin/targets`, `POST /v1/admin/targets/{slug}/progress` |
| `features/knowledge/channels/http.py` | `POST /v1/knowledge/search`, `PATCH /v1/knowledge/sources/{source_id}` |
| `features/proactive/channels/http.py` | `GET /v1/proactive/feed`, `POST /v1/proactive/feed/{nudge_id}/feedback`, `POST /v1/proactive/feed/{nudge_id}/read` |
| `features/stream/channels/http.py` | `GET /v1/me/streams`, `DELETE /v1/me/streams/{stream_id}` |
| `features/stream/channels/public_http.py` | `GET /v1/streams/live/bans`, `DELETE /v1/streams/live/bans/{principal}` |
| `features/subtitles/channels/http.py` | `POST /v1/subtitles/interpret`, `POST /v1/subtitles/recognize` |

---

## 8. Cross-slice dependencies

Derived from the draft's imports between modules of different v2 owners. In v2 every edge is a published contract: a port in `features/<x>/contracts`, an outbox event, or HTTP. "Everyone → S01 (current user)" and "everyone → S03 (entitlements)" are omitted from the rows.

| From | To | Contract in v2 | Draft evidence |
|---|---|---|---|
| all slices calling models | F6 (FM-4) | Provider port: `complete`, `stream`, `transcribe`, `embed`, `rerank`, `image`, each with an effect key; returns usage and writes the cost row | `services/llm/*` imported by S01, S03, S04, S05, S06, S07, S09, S10, S14, S17 |
| S01, S03, S08, S12, S14, S15, S16 | F6 (FM-4) | Email port: enqueue a templated message on the `critical` or `bulk` queue | `services/email/notify`, `tasks/send_email` |
| every slice declaring periodic jobs | F6 (FM-4) | Periodic-job registry: name, interval, task; one run per interval across both homes | `ScheduleDefinition` in 12 feature modules, `entrypoints/scheduler_loops.py` |
| S01, S04, S05, S06, S07, S09, S14, S15, F5 | S03 | `Entitlements` port: snapshot, quota, `require_paid`, `require_quota` | `features/billing/contracts` |
| S04 | S07 | Context graph port: project a meeting into people, commitments, decisions; positions over time | `features/context_graph/contracts` (12 imports) |
| S04 | S09 | Memory port: write recollections of a meeting | `features/memory/contracts` |
| S04 | S16 | Hub port: assign a meeting to a hub | `features/hub/contracts` |
| S04 | S08 | Storage port: save a meeting as a file | `services/storage` |
| S04 | S12 | Calendar port: put an event proposed by the meeting into the calendar | `features/meetings/contracts/ports.CalendarPort`, `infrastructure/calendar_adapter` |
| S12 | S04 | Meeting read port: notes and summary pushed to Notion, Slack, CRM on the user's request | `api/me_integrations.py` |
| S05 | S04 | Transcript port: append lines by `(session_id, seq)`; start a run on end | `features/meetings/channels` |
| S05 | S09 | Agent port for voice turns; user context for live answers | `services/agent`, `user_context_service` |
| S05 | S07 | Knowledge retrieval port for live answers | `composition.providers.knowledge` in `api/realtime_prompts.py`; legacy `rag_pipeline` (FM-2) |
| S05 | S06 | Room pass verification for subtitles | `core/livekit` |
| S06 | S04 | Meeting port: create the room owner's meeting, hand over the recording or track transcript | `features/meetings/{application,channels,contracts}` |
| S06 | S08 | Storage port: room recordings | `services/storage` |
| S07 | S12 | Connector files port: read documents of connected services | `features/connectors/contracts` (9) |
| S07 | S08 | Storage port: originals of knowledge documents | `services/storage` (6) |
| S08 | S07 | Knowledge port: send a file to the knowledge base | `features/knowledge/contracts` |
| S09 | S04 | Meeting retrieval and folder ports for Leo's tools | `features/meetings/channels/agent_tools`, `meeting_org` |
| S09 | S07 | Search and context graph ports | `features/context_graph/contracts`, `knowledge/contracts` |
| S09 | S11 | Errands port: schedule, cancel, list | `features/errands/{contracts,application}` (9) |
| S09 | S12 | Connector actions, mail and calendar ports | `features/connectors/contracts` (14), `services/calendar` |
| S09 | S13, S08, S15, S16 | Tracker, storage, support and hub ports for Leo's tools | `services/agent/tools/{tracker,storage,support,hub}` |
| S09 | S10 | External MCP tools in the agent | `services/mcp`, `mcp_connection_auth` |
| S10 | S09 | Agent tool registry exposed as MCP tools | `services/agent/registry` |
| S11 | S12 | Connector actions executed by an errand | `features/connectors/contracts` |
| S12 | S06 | Stream contract for calendar events of type "broadcast"; rooms of calendar meetings | `features/stream/contracts`; `services/calendar/event_service.py`, `notifications.py` read rooms |
| S12 | S10 | MCP connections reused by integrations | `services/mcp` |
| S13 | S12 | Jira link of a project | frontend `tracker` calls `/me/jira` |
| S14 | every slice | Events through the outbox → analytics facts | `analytics__facts` consumer |
| F5 | S01, S03, S15, F6 | Events through the outbox → Telegram alerts | `alerting` consumers |
| S15 | S01, S03, S14, F6 | Admin HTTP APIs read by the `platform-admin` screens | frontend `platform-admin` |
| S17 | S04, S06 | Link preview pages share one markup module | `web_share.py` |
| every slice with company resources | S02 | Access policy: one check inside the reading query; `resource_grants`; audit event in the same transaction | new in v2 (§7) |
| every slice storing user data | S01 | Deletion and export registry: tables, S3 prefixes, external grants | `services/account_data.py` |

---

### 3.3 Screens of the new web UI without a draft feature

The new web UI ([ADR 0022](../adr/0022-new-web-design-replaces-draft-parity.md)) has two screens no draft feature covers. Assigned by the owner on 2026-10-08 (F2-D6, [F2 plan](packages/F2-frontend-foundation.md) §3):

| Frontend slice | Screen | v2 |
|---|---|---|
| `mail` | `/app/inbox`: mailbox with Leo's insights | S12 (mail is read through connectors) |
| `productivity` | `/app/productivity`: the user panel's home — today's brief, tasks, meetings, shares | S16 |

---

## 9. Changes to the plan made by D4

- `features/stream` and the frontend `streams` move from S05 to S06: broadcasts run on LiveKit passes, the SFU data channel and egress, like rooms.
- `features/meeting_assistant` goes to S06: it serves the room's AI panel with room-pass authentication.
- `features/subtitles` stays in S05 and depends on S06 for room passes.
- S09 owns the `models` feature on both sides, including `/admin/ai-models`; S15 no longer lists the model registry.
- Admin APIs belong to the slice that owns the data; S15 owns the `platform-admin` screens, users, dashboard, monitoring and support.
- `features/context_graph` stays in S07; `features/proactive` (with Web Push) stays in S09.
- `features/alerting` goes to F5, `features/demo` and `features/docs_assistant` to S17 (FM-1), the top-bar ticker to S16.
- S11 is renamed "Errands": periodic jobs move to F6 (FM-4).
- F6 Platform services is added between F1 and S01 (FM-4).
- The `slice` field of `contracts/draft/consumers.json` (D1) was set from the plan before D4. Where it differs, this map wins: admin routes belong to the slice that owns the data (`admin/tariffs`, `finance`, `payments`, `promocodes`, `affiliates` → S03; `admin/models`, `prompts`, `context` → S09; `admin/costs`, `abuse` → F6; `admin/livekit` → S06; `admin/app_builds` → S16; `admin/analytics`, `client_errors` → S14), `features/stream`, `features/whiteboard`, `features/meeting_assistant` and `web_stream.py` → S06, `features/demo` and `features/docs_assistant` → S17, `api/ticker.py` → S16, `api/unsubscribe.py` → S15.
- Routes without a consumer are dropped, except four (FM-5); `api/transcripts.py`, `api/prompts.py` with `services/deepseek_proxy.py`, `api/me_affiliate.py`, `api/me_recordings.py`, `api/admin/sessions.py`, `api/admin/storage.py` and the legacy notes API disappear entirely. S17 now needs F1 and F6 as well as F2, because the landing demo and the help-centre assistant call models.
