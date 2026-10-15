# Slice map: the feature slices of Shosai

The feature slices of Shosai, derived from the product: the new cabinet in `frontend/`, the [philosophy](../../.claude/CLAUDE.md#philosophy), the [target architecture](../design/ARCHITECTURE.md) and the [Leo architecture](../design/leo/ARCHITECTURE.md). Prompt: [prompts/SLICE-MAP.md](prompts/SLICE-MAP.md).

- **Status:** approved by the owner on 2026-10-13 with the decisions of [§8.1](#81-decided-by-the-owner-on-2026-10-13); applied the same day ([§9](#9-after-approval)). This map is the plan of record for the feature slices: it replaced the S01–S17 cut of [REWRITE_PLAN.md](REWRITE_PLAN.md) §3 Phase 2 ([ADR 0038](../adr/0038-feature-slices-derived-from-the-product.md)); [FEATURE_MAP.md](FEATURE_MAP.md) stays the inventory of the draft. Where the body of §2–§7 and §8.1 differ, §8.1 wins; the cards of §4.2 already carry it.
- **Method:** every route, slice, `api/` and `mocks/` layer of the cabinet read on 2026-10-13 (31 frontend slices, ≈ 100 000 lines); the D1 contract baseline (`contracts/draft/`); target architecture §1–§22; Leo architecture in full; REWRITE_PLAN, STATUS, FEATURE_MAP, DATA_MAPPING; the F6 plan.
- **Reading guide.** §1 states the rules of the cut. §2 is the capability inventory, screen by screen. §3 maps the native and external contracts to owners. §4 lists the slices with their scope, data, routes, dependencies and Leo tools. §5 gives the build order. §6 compares with S01–S17. §7 lists what F6 and DATA_MAPPING must change. §8 holds the owner's decisions. §9 is the follow-up after approval.

---

## 1. Rules of the cut

1. **One business capability per slice, named for what it does in Shosai.** A slice owns its tables, its `/v1` routes, its events, its Leo toolset and its screens. Backend `features/<name>/` and frontend `src/features/<name>/` carry the same name (CLAUDE.md "Architecture"); §4.3 lists the frontend renames this requires.
2. **One owner per entity.** Where the cabinet keeps one thing in several places (three task lists, two "connect a source" screens, three plan enumerations, two default models, two operator directories), the cut gives it one owner and the other screens read it through that owner's contract. Each such merge removes work from the user, in the philosophy's terms (§2.10).
3. **Integration through contracts, events and shared context only.** Ports in `features/<x>/contracts`, outbox events with ids only (§12), and the HTTP API. Leo's tools live in the slices that own the data, as `ToolSpec`s (ADR 0029).
4. **Composition screens own no data.** The home screen (`/app/productivity`), the Meetings overview (`/app/meetings`), the Settings dialog and the admin dashboard compose widgets of several owners. Each widget calls its owner's API; there is no aggregating backend slice and no request waterfall (independent calls run in parallel).
5. **The cabinet's mock paths are not the contract.** Mocks call `/api/...` with mixed casing (the hub uses camelCase) and two error shapes (`{detail:{code}}`, `{detail: string}`). Each slice designs its `/v1/...` OpenAPI first — snake_case, the ADR 0008 envelope, cursor pagination with a maximum page size (§10) — and its frontend step moves the screens to the generated client.
6. **Push is added, polling stays bounded.** Today every screen loads once and polls every 1.5 s only while something is busy (indexing, syncing, analysing). That stays. Push comes with `proactive` (`/v1/ws/user`): additive frames that carry ids and an `invalidates` domain, so screens refetch instead of polling. No slice opens its own socket.
7. **No capability without a consumer.** A draft capability with no screen, no shipped native client and no external caller is not carried over (FM-5 applied to whole capabilities). A capability the cabinet shows but the architecture forbids is raised in §8, not built quietly.

---

## 2. Capability inventory

Columns: **Needs** — what the screen asks of the backend (calls, data, realtime, background work); **Leo** — Leo's part on that screen; **Serves** — what it takes off the user: **Re**member, **Tr**ack, **Co**nnect, **Wa**tch, **Or**ganise, **Cd** coordinate; **Slice** — the owner (§4).

### 2.1 Frame, sign-in, settings

| Screen / state | Needs | Leo | Serves | Slice |
|---|---|---|---|---|
| Sign-in, registration, reset, desktop connect | Not in the cabinet: no `/login`, `/register`, `/connect` route; the cabinet assumes a cookie session (`lib/api/client.ts` defers CSRF and refresh to "S01") | — | — | identity (§8 SM-7) |
| Shell: user menu, Log out, current user | `GET /v1/me` (missing; the shell shows `DEMO_USER`), logout (an empty menu item today), 401 → sign-in redirect, interface language (cookie only) | — | Or | identity |
| Shell: sidebar, workspace switcher | `GET` workspaces of the account | — | Or, Cd | workspaces |
| Shell: command palette (⌘K) | Jumps to pages only, client-side; no content search | — | Or | — (client) |
| Shell: header weather | Browser → Open-Meteo directly; ignores Settings › Privacy `share_location` (a frontend fix) | — | — | — (client) |
| Settings › Account | Profile (name, display name, work role), avatar upload, delete account (re-typed email) | name used in greetings | Re | identity |
| Settings › Privacy | `improve_models`, `share_location`, full export (archive), per-kind data lists (shared chats, artifacts, uploaded files, feedback) | — | — | identity; the export and deletion registry spans every slice |
| Settings › Billing, Usage | Plan, invoices, payment methods via the acquirer's hosted portal; weekly token limits per tier, frontier spend per model, token packs | — | — | billing |
| Settings › Leo | Model ("auto" or a model from Studio's catalogue), answer language, length, switches for web search, voice, knowledge, connected services | the settings Leo runs under | — | agent (`/v1/agent/settings`) |
| Settings › Memory | On/off; a model-written summary with "ask or update"; no list of single facts (the mock has `GET/DELETE /memories` but no UI calls it) | memory summary | Re | memory (§8 SM-6) |
| Settings › Connectors | 12 apps (Gmail, Outlook, Drive, Dropbox, Yandex Disk, Notion, Confluence, Slack, GitHub, GitLab, Jira, HubSpot), OAuth popup with PKCE through `/oauth/callback`, disconnect revokes | Leo reads and acts through them | Co | connectors |
| Settings › MCP | Remote MCP servers for Leo: URL, transport, write-only auth header, probe, tool count | external tools in Leo | Co | mcp |
| Settings › Hotkeys | 8 global shortcuts of the desktop app; read by the native client (`GET /v1/me/hotkeys`) | — | — | capture |
| Preferences (theme, layout, font) | Cookies and localStorage only; nothing on the server | — | — | — (client) |

### 2.2 Recorded meetings: Notes and Meetings

| Screen / state | Needs | Leo | Serves | Slice |
|---|---|---|---|---|
| `/app/notes` library (timeline, grid, list) | List of recordings; folders CRUD with colour; move by drag; delete with Undo (soft); export transcript (client-side) | — | Re, Or | meetings |
| Upload a recording (≤ 25 MB, audio/video) | Presigned upload, then transcription → write-up run; "Transcribing…" status (waits forever today: nothing is wired) | — | Re | files (upload) → meetings (run) |
| `/app/notes/:id` header | Participants (add or remove by email), folder, hub chip | hub suggestion ("Looks like X") | Re, Co | meetings; the hub chip is hubs |
| Tab "Notes" | The user's own Markdown notes, autosaved; written on the web or synced from the desktop app (`PUT …/note/draft` is native) | — | Re | meetings |
| Tab "Enhanced" | Leo's write-up by a template; 8 shipped templates, user templates, "Regenerate" as an async run | writes summary, key points, decisions, action items | Re, Tr | meetings |
| Tab "Transcript" | Transcript with speakers, search, deep link `?t=` | — | Re | meetings |
| Tab "Mind map" | Map tree from the write-up | builds the map | Re, Co | meetings |
| Action items | Checkboxes; once shared to a workspace they become that workspace's tasks — two checkbox systems today | extracts owners and dates | Tr | tasks (§8 SM-3) |
| Share › Link | One link per meeting: show transcript, show names, comments, expiry; revoke deletes comments | — | Cd | meetings |
| Public shared note `/s/:token` | Unauthenticated read; anonymous comments (rate-limited) — component exists, no route mounts it | — | Cd | site renders, meetings serves |
| Share › Workspace | Share a recording into a workspace with an audience, project, transcript flag; moves it if shared elsewhere | — | Cd | workspaces |
| `/app/meetings` overview (all, upcoming, live, past) | Read model: calendar events with conference links + recordings + "Shared with you" + minutes allowance; live status from the client clock | "Prepare me for my next call" | Wa, Cd | composition: calendar, meetings, workspaces, billing |

**Background work:** transcription with diarisation; the post-meeting pipeline (write-up, decisions, action items, map) — also when the client never ends the meeting (inv-7); template regeneration; share-link expiry; per-minute meeting windows indexed for search.

### 2.3 Live capture (desktop clients)

The cabinet has no live screen; capture happens in the shipped macOS and Windows clients and is the largest native contract (§3).

| Surface | Needs | Leo | Serves | Slice |
|---|---|---|---|---|
| Desktop recording | `WS /v1/ws/realtime`: audio frames → `transcript` lines with server `seq`, durable queue before the frame (inv-6), resume, `ask`, `vision`, `answer.*` | in-meeting hints and answers through the agent port, user context from memory and studio | Re, Wa | capture |
| Phone-to-Mac translation relay | `WS /v1/ws/sessions/{id}` | — | Cd | capture |
| Simultaneous voice translation | `POST /v1/ai/voice-translate/{token,usage}`, `WS /v1/ws/voice-translate` | — | Cd | capture |
| Studio roles for the desktop assistant | prompts and models per role (`live_answers`, `screenshots`, `code`, `system_design`, `notes`, `transcript`) | — | Re | studio |

### 2.4 Leo

| Screen / state | Needs | Leo | Serves | Slice |
|---|---|---|---|---|
| Leo panel (every page, ⌘I; scopes Personal, workspace, hub) | Today `POST /api/leo` with the whole history from localStorage, NDJSON stream. Needed: server threads per scope, SSE v2 with resume (ADR 0024, 0032) | the agent | all six | agent |
| Step timeline, "Needs approval" badge | The badge is only a label: no approve or reject UI or endpoint. Needed: action cards and an approvals inbox (ADR 0025) | proposals | Cd | agent |
| Voice mode | Browser Web Speech only; transcripts sent as messages; no server voice | — | — | agent (client) |
| Attachments (≤ 5 × 10 MB) | Presigned upload, digests in context | reads them | — | files → agent |
| Leo in the admin panel | Russian suggestions ("Какие обращения ждут ответа?") imply admin toolsets | — | — | §8 SM-12 |
| Leo feed "Today", in-context chips | Not in the cabinet yet (Leo architecture §13.3) | initiative | Wa | proactive |

### 2.5 Files and knowledge

| Screen / state | Needs | Leo | Serves | Slice |
|---|---|---|---|---|
| `/app/file-manager` (gated by `file_manager_gb`) | Files and folders CRUD, star, move, duplicate, upload ≤ 20 × 2 GB, delete with Undo; **no download, open or preview** (a gap) | "Use with Leo" per file or folder | Or | files |
| Share or transfer a file to a workspace | publish as workspace knowledge; transfer of ownership | — | Cd | workspaces (knowledge item) over files |
| Indexing badges (queued → parsing → chunking → embedding → indexed) | Index pipeline, polling while busy, quota `knowledge_base_mb` (409) | — | Re | knowledge |
| `/app/knowledge-base` › Files | Index settings, chunk counts, pick files and folders for Leo, re-index | — | Re | knowledge over files |
| › Sources | 12 connectors with scoping (JQL, channels, folder, site), website crawl, "Sync now", status | — | Co, Wa | knowledge (sync) over connectors (grant) |
| › From workspaces | Read-only counts per workspace | — | Co | workspaces |

**Load flag:** sources are connected in two places (Settings › Connectors and Knowledge › Sources) with overlapping lists. One connection registry in `connectors`; Knowledge › Sources picks a connection and a scope (§8 SM-13).

### 2.6 Calendar and mail

| Screen / state | Needs | Leo | Serves | Slice |
|---|---|---|---|---|
| `/app/calendar` month, week, day | Events CRUD, drag and resize, recurring series, several calendars, focus blocks; **no API today** (local state); two-way sync with Google, Microsoft, CalDAV; conference links; attendees (missing in the model, needed by Meetings) | find free time, create, move, cancel (approval) | Or, Cd | calendar |
| Upcoming meetings in hubs, workspace home, Meetings | Upcoming events with attendees resolved to people or members | meeting prep | Wa, Cd | calendar → read by hubs, workspaces |
| `/app/inbox` (and the `/app/mail` preview) | Today only `GET /api/mail/insights`; the mailbox is local. Needed: mailboxes through connectors (Gmail, Outlook), list, thread, flags, archive, trash, drafts, send; push of new insights | triage "needs you / fyi / low", next step, reply-by, summary, draft in the user's voice; send is an approval | Wa, Tr, Cd | mail (§8 SM-14) |

### 2.7 Work: tasks, hubs, home

| Screen / state | Needs | Leo | Serves | Slice |
|---|---|---|---|---|
| `/app/kanban` boards (board, list, table) | Boards with templates and icons, columns, card order with revision, tasks with priority; Jira boards in two-way sync with webhooks; "show my workspace tasks here" | "Which tasks are overdue?" | Tr, Or | tasks |
| Kanban inert controls | Filter, Sort, Import CSV, From template, Automation have no handler | — | — | dropped from the UI (§2.10) |
| Workspace tasks, "Needs you", My workspace tasks | One task store with assignee, due date, project, source meeting | tasks from meetings | Tr, Cd | tasks |
| Home `/app/productivity` | Greeting, "Today" list (local, lost on reload), workspace tasks, projects (static), calendar (no events), recent notes (static), focus timer (localStorage), year skyline with streaks (random data) | "Plan my day" | Tr, Wa | composition: tasks, calendar, meetings, proactive (§8 SM-4) |
| `/app/hub` list | Hubs with computed summary (top gap, rhythm, open topics), board link, archive | — | Or, Wa | hubs |
| Hub "Today" brief, "Coming up" prep | Fires across hubs (≤ 7), prep per upcoming meeting with its hub's open topics and materials | — | Wa, Cd | hubs |
| `/app/hub/:id` | Charter (human-written only), unresolved topics with stage, gap, rounds, evidence quotes; done, dismiss for 90 days, assign; digest since the last meeting; feed of facts per meeting; materials (links, uploads, meeting summaries) | daily "going in circles" signal; answers only inside the hub | Tr, Wa, Re, Co | hubs over commitments |
| Topic sheet | Stage track, rounds with blockers, decision vs reversed decision, links between topics | — | Tr, Co | commitments |

**Background work:** classification of a meeting into a hub (series, subject, title, entity, organisation) with series memory; facts per meeting (decision, promise, risk, problem, question) with speaker and timestamp evidence; clustering into topics; gap detection against "now" (overdue, due soon, forgotten, undated, orphan decision, unanswered, silence, contradiction); dismissal expiry; Jira import and webhooks.

### 2.8 Workspaces

| Screen / state | Needs | Leo | Serves | Slice |
|---|---|---|---|---|
| `/app/w`, `/app/w/new` | List of the account's workspaces; create (name, seats 2–100, trial) | — | Cd | workspaces; trial and seats in billing |
| Gate | 404 for missing or not a member, 423 when suspended | — | — | workspaces |
| Home | Setup checklist (derived), Needs you, Coming up (where notes will go), projects, recent decisions | — | Tr, Wa | composition: tasks, calendar, workspaces, commitments |
| Decisions log | Decisions of meetings visible to the viewer, with supersession; read-only | extracts and links them | Re, Tr | commitments |
| Meetings, meeting detail | Shared recordings with audience participants / team / workspace, project, transcript flag; organiser or admin edits; Undo | summary, key points | Re, Co | workspaces (share record) over meetings (content) |
| Members, teams, invitations | Seat meter, invite by email (≤ 20, seat-limited), resend, revoke, roles, teams (private flag), remove with cascade | — | Cd | workspaces |
| Projects, project detail | Projects with status, lead, team, target; page aggregates tasks, meetings, decisions, files by `project_id` | — | Or, Tr | workspaces (§8 SM-2) |
| Knowledge | Uploads, published personal files, connected sources; access workspace or team; indexing status | answers with the member's rights only | Re, Co | workspaces (items) over knowledge (index) |
| Settings | Rename, join by company email domain, sharing defaults, plan and usage per member, delete or leave | — | — | workspaces; plan in billing |
| Auto-share at meeting end | Previewed (`shares_with`), not implemented | — | Cd | workspaces (on `meetings.notes_ready`) |

**Missing in the UI:** accepting an invitation and joining by domain have no endpoint or screen. **Leaks to fix server-side** (nfr-15): `GET /workspaces/{id}` returns private teams, pending invitation emails and every member's `last_active_at` to all members; the client filters them.

### 2.9 Upgrade, support, downloads

| Screen / state | Needs | Leo | Serves | Slice |
|---|---|---|---|---|
| `/app/upgrade` | Public plan catalogue, current and effective plan (a workspace seat overrides), minutes meter, hosted checkout, sales inquiry | — | — | billing |
| Feature gates | `file_manager_gb`, `knowledge_base_mb`, `meeting_minutes_per_month` | — | — | billing (entitlements port) |
| `/app/support` | Tickets with category, thread, attachments, reopen, rating; no notification of a reply | create a ticket | Tr, Cd | support |
| `/app/download` | Latest build per platform and channel, checksums, staged rollout by install id | — | — | releases |

### 2.10 Admin panel

| Screen | Needs | Owner |
|---|---|---|
| Dashboard (Analytics, CRM, CRM v1) | All static template data; CRM and CRM v1 duplicate each other and are unrelated to Shosai | composition (§8 SM-12) |
| Users | Static template; needed: search, account card with the user's AI spend (F6 report), block, ban with refund | identity |
| Roles | Static template of 12 generic roles; nothing maps to the admin screens; the frontend guards nothing | identity (operator roles, §8 SM-12) |
| Profile | An HR employee template | dropped (§8 SM-12) |
| Workspaces | List with KPIs, detail with members, events, content counts; seats, owner transfer, suspend, resume, delete | workspaces |
| Plans, Promo codes | Catalogue with prices per currency, limits, capabilities, archive; promo codes with scope and limits | billing |
| Billing | MRR, revenue, churn, ARPU, refunds per currency; transactions with refunds and invoices | billing |
| AI models | Provider credits, spend today, month, forecast; model catalogue with enable and default | studio (catalogue) over F6 (spend reports) |
| Platform prompts | Draft, publish, versions of the system prompt, behaviour, guardrails, feature prompts | studio |
| LiveKit | Server, nodes, rooms, participants, egress; end room, disconnect; 10 s polling | rooms |
| Apps | Releases per platform, channel and arch; upload with SHA-256, publish, revoke, rollout | releases |
| Errors, issue | Issues grouped by fingerprint, regressions, crash-free rate (needs desktop session telemetry), assignee, link to support; ingest from clients | telemetry |
| Support | Three-pane inbox, notes, canned replies, assignee, priority; 5 s polling. Its contract (`conversations`) differs from the user's (`tickets`): one ticket store | support |

### 2.11 Load flags and how the cut treats them

| Flag | Treatment |
|---|---|
| Three task stores (kanban cards, workspace tasks, the home "Today" list) and two checkbox systems for meeting action items | One task store in `tasks` (§8 SM-3) |
| Two places to connect sources | One connection registry in `connectors` (§8 SM-13) |
| Year skyline with streaks on the home screen — gamification the hub explicitly rejects ("no streaks") | Dropped (§8 SM-4) |
| Plan identity enumerated four ways (catalogue, billing `PLANS`, support `SupportPlan`, workspace plan name) | One catalogue in `billing`; others reference it by id |
| "Default model" twice (AI models, platform prompts) | One, in `studio` |
| Operator directory twice (error assignees, support teammates) | One, in `identity` |
| Owners as free text (hub topics, kanban cards) | People from `commitments` and members from `workspaces` |
| Manual filing: folders, hubs, projects | Kept, with Leo's suggestions (A1/A3 in `proactive`) and the hub's series memory |
| Kanban controls without behaviour | Removed from the UI until a need appears |
| Two usage meters on two screens (minutes per month, tokens per week) | One usage view owned by `billing`, shown in Settings › Usage and Upgrade |
| Support replies and task assignments notify nobody | Kinds of the one proactive pipeline (`support.replied`, `tasks.assigned`) with its budgets and quiet hours; email only where the user asked |
| Leo approvals do not exist; chats live in localStorage | Action Gateway and server threads in `agent` |
| Memory facts cannot be seen one by one | Facts list with sources in `memory` (§8 SM-6) |
| Error ingest under `/admin` with a client key | A public client path in `telemetry` |

---

## 3. Native and external contracts → owner

From `contracts/draft/consumers.json` and `websocket.json` (D1). **N** native (macOS 1.4.5, Windows 1.4.5; nfr-12), **E** external.

| Owner | Class | Routes and frames |
|---|---|---|
| identity | N | `POST /v1/auth/login`, `POST /v1/auth/refresh`, `POST /v1/auth/logout`, `GET /v1/auth/me`, `POST /v1/auth/desktop/exchange`, `POST /v1/auth/desktop/refresh`; the browser connect page `GET /app/connect?state=` (cabinet standalone route) |
| identity | E | `GET /v1/auth/social/{provider}/callback`, `GET /v1/auth/social/yandex/token-page` |
| edge + site | N | `GET /`, `GET /{path}` fallback redirects into `/app/…` (including `/cabinet/leo?reminder=` with `%3F`), `/models`, `/knowledge-base` |
| meetings | N | `POST /v1/sessions`, `PATCH /v1/sessions/{id}`; `GET /v1/me/sessions` (limit/offset kept beside a cursor), `GET …/{id}/full`, `PATCH`, `DELETE`; `POST /v1/me/sessions/import`, `GET …/import/{job_id}`; `GET …/{id}/note`, `PUT …/note/draft`; `PATCH …/note/action-items/{item_id}` (writes through to `tasks`); `POST …/audio/init`, `PUT …/audio/{run_id}/part/{n}`, `GET …/audio/{run_id}`, `POST …/complete`, `DELETE …/audio/{run_id}` |
| meetings + site | E | `GET /r/{token}` (meeting result link: site renders, meetings serves) |
| capture | N | `WS /v1/ws/realtime` (11 client, 15 server frames), `WS /v1/ws/sessions/{id}`, `WS /v1/ws/voice-translate`, `POST /v1/ai/voice-translate/token`, `POST /v1/ai/voice-translate/usage`, `GET /v1/me/hotkeys` |
| agent | N | `POST /v1/ai/chat/stream`, `POST /v1/ai/vision/analyze` (raw model proxy through the provider port) |
| proactive | N | `WS /v1/ws/user`: `hello`, `ping`/`pong` (exact literal), `ack`, `reminder.due`, `reminder.settled`; new frames additive |
| errands | N | `POST /v1/errands/{id}/snooze`, `POST /v1/proactive/reminders/{id}/done` |
| telemetry | N | `POST /v1/analytics/collect`, `POST /v1/client/errors` |
| telemetry | E | `POST /v1/client/csp-report` |
| billing | E | `POST /v1/billing/webhook/{provider}`, `…/{provider}/{kind}` (tbank, cloudpayments, lava, lava_paypal, legacy moneta) |
| calendar | E | `GET /v1/integrations/oauth/{google,microsoft}/callback`, `POST /v1/integrations/google/notifications`, `POST /v1/integrations/microsoft/notifications`, `GET /v1/calendar/export.ics` |
| tasks | E | `GET /v1/jira/oauth/callback`, `POST /v1/jira/webhook/{link_id}` |
| connectors | E | `GET /v1/integrations/oauth/{slack,notion,attio,hubspot}/callback` (§8 SM-11); Nango's own `/nango/*` stays an edge route to the Nango server |
| mcp | E | `GET/HEAD /.well-known/oauth-authorization-server`, `GET/HEAD /.well-known/oauth-protected-resource`, `GET/POST /mcp`, `POST /v1/mcp/oauth/{register,token,revoke}`, `GET/POST /v1/mcp/oauth/authorize`, `GET /v1/mcp/oauth/callback` |
| knowledge | E | `GET /v1/knowledge/vault/status`, `GET /v1/knowledge/vault/manifest`, `POST /v1/knowledge/vault/notes` (Obsidian plugin) |
| rooms | E | `POST /v1/livekit/webhook`; links already sent: `GET /j/{token}`, `/meet/{token}`, `/rooms/join/{token}`, `/live/{token}` (§8 SM-8) |
| releases | E | `GET /v1/app/builds/{id}/download` |
| F6 (email) | E | `GET/POST /v1/unsubscribe`, `GET /email/{name}` (images in sent emails) |
| site | E | SEO pages, help centre `/docs/*`, `robots.txt`, sitemaps, `llms*.txt`, verification files, `/assets`, `/fonts`, `/img`, `/files`, `/og*` |
| F2 (cabinet) + edge | E | `GET /app`, favicons, icons, `manifest.webmanifest` |

Rules the harness cannot check stay with their owners: TLS chain and base URL (F4); unknown `/v1` paths answer JSON 404 (F1); `detail` shapes and camelCase keys of note and import responses (meetings); captcha exemption and CSRF on cookie refresh (identity); WS auth by header or subprotocol, accept then close 1013 when full (capture).

---

## 4. The slices

### 4.1 Catalogue

| # | Slice | What it does for the user | Domain in §5 of the architecture |
|---|---|---|---|
| 1 | `identity` | One login for web and desktop; profile and privacy; export and deletion of everything; operator accounts | identity |
| 2 | `workspaces` | Shared team space: members, teams, roles, seats, sharing, the access policy and audit for every slice | organizations (renamed, §8 SM-15) |
| 3 | `billing` | Plans, entitlements, usage meters, payments, seats, company invoices | billing |
| 4 | `files` | The user's files, uploads and quota — the one path for bytes | — (S08 storage) |
| 5 | `meetings` | Every recorded meeting becomes notes, transcript, map and facts | meetings |
| 6 | `capture` | Live capture, live answers and live translation on the desktop | realtime (renamed) |
| 7 | `knowledge` | Indexing and search over files, notes, sources and meetings | knowledge |
| 8 | `commitments` | People, decisions, promises and open topics across all meetings | new (the draft's context graph) |
| 9 | `hubs` | One place per client or piece of work that watches what is unresolved | new as a slice (S16 hubs) |
| 10 | `tasks` | One task list: boards, meeting action items, workspace tasks, Jira | new as a slice (S13 tracker) |
| 11 | `calendar` | One calendar over connected calendars, with meetings and focus time | new as a slice (from S12) |
| 12 | `mail` | Leo reads the inbox, says what needs the user and drafts replies | new |
| 13 | `connectors` | One registry of connected services and their grants | connectors |
| 14 | `agent` | Leo: threads, runs, tools, Action Gateway, skills | agent |
| 15 | `decisions` | Leo's Decision Layer over Jev, also used by mail and hubs | decisions |
| 16 | `memory` | What Leo knows about the user, visible and correctable | memory |
| 17 | `proactive` | Leo's initiative: signals, suggestions, the Today feed, push | proactive |
| 18 | `errands` | Delayed Leo actions and reminders | errands |
| 19 | `studio` | How Shosai's AI behaves: models, prompts, personal context | models (extended, §8 SM-5) |
| 20 | `mcp` | Shosai as an MCP server; external MCP servers for Leo | — |
| 21 | `support` | Tickets and newsletters between operators and users | — |
| 22 | `releases` | Desktop builds, staged rollout, downloads | — |
| 23 | `telemetry` | Client errors as issues; product events; the satisfaction survey | analytics (renamed) |
| 24 | `rooms` | Shosai video rooms with per-speaker transcription, broadcasts and the room whiteboard | rooms |
| 25 | `site` | The public site and public pages of shared links (S17) | — |

The home screen, the Meetings overview, the Settings dialog and the admin dashboard are composition screens (§1 rule 4).

### 4.2 Slice cards

Each card: **Scope** · **Owns** (tables; draft sources from DATA_MAPPING) · **Routes** (native N, external E, plus the `/v1` area it designs) · **Depends on** (contracts it calls) · **Emits** (outbox events) · **Leo tools** (toolset; W = write through the Action Gateway).

#### 1. identity
- **Scope:** registration, email verification, password, social sign-in, cookie sessions with CSRF and rotation, desktop browser sign-in, devices and sessions (FM-5 kept), `GET /v1/me`, logout; directory by `HMAC(email)` and home routing; account transfer saga; profile, avatar, privacy switches, interface language; cross-border consent (nfr-14); the export and deletion registry every slice registers in (§14 rule 7); operator accounts and operator roles; admin users screen.
- **Owns:** `users`, `directory_entries`, `refresh_sessions`, `password_reset_tokens`, `login_events`, `user_identities`, `user_consents`, `pending_registrations`, `data_export_jobs` (O9), `account_deletions`, `home_transfers`, `operator_audit_events` (EU home; the admin signs in from the environment, ADR 0049); desktop codes and registration routing in Valkey; `user_onboarding` dropped (SM-10). Plan: [slices/identity.md](slices/identity.md).
- **Routes:** N and E per §3; `/v1/auth/*`, `/v1/me*`, `/v1/admin/users*`. Sign-in screens per §8 SM-7.
- **Depends on:** F6 (email, consent flag in `CallContext`), billing (entitlements in `/me`).
- **Emits:** `identity.account.registered`, `identity.account.deletion_scheduled`, `identity.account.deletion_cancelled`, `identity.account.deleted`, `identity.account.transferred`, `identity.account.blocked`, `identity.sessions.revoked` (three-part names, core's event rule; [ADR 0045](../adr/0045-identity-sessions-registration-and-deletion.md)).
- **Leo tools:** `account` toolset (read profile and plan summary with billing; `navigate` is core).

#### 2. workspaces
- **Scope:** create a workspace, members, invitations (email, link, verified domain), roles owner/admin/member/guest, teams, seats (with billing), sharing defaults, auto-share at meeting end, suspension, deletion and leave cascades, the per-member usage table, projects; the share records that put a member's meeting or file into the workspace; workspace knowledge items (upload, published file, connected source) and their access; **the access policy** (one check inside each reading query, `resource_grants`, `org_id` and `access` columns, RLS policies) and `org_audit_events` for every slice; admin workspaces screen. At launch a person joins only workspaces of their own home: invitations and domain joins across homes are refused with an explicit error (§8.1 SM-1, [ADR 0039](../adr/0039-one-account-per-person-with-workspaces.md)).
- **Owns:** `organizations`, `memberships`, `invitations`, `teams`, `team_members`, `projects`, `resource_grants`, `org_audit_events`, `workspace_meeting_shares`, `workspace_knowledge_items`, `directory_domains`. The draft has none of these (R3: company tables start empty).
- **Routes:** no native or external; `/v1/workspaces/*`, `/v1/me/{shares,meetings,knowledge}`, `PUT /v1/{resource}/{id}/access` (§10), `/v1/admin/workspaces*`.
- **Depends on:** identity (principal, token version bump on removal), billing (seats, plan, trial), meetings, files, knowledge (read contracts for shared content), tasks (cascade: open tasks unassigned), F6 (invitation email).
- **Emits:** `workspaces.member_joined`, `.member_removed`, `.access_changed`, `.meeting_shared`, `.knowledge_item_added`.
- **Leo tools:** `workspace` toolset: members and teams (read), share a meeting (W), set access of a knowledge item (W).

#### 3. billing
- **Scope:** plan catalogue with prices per currency, limits and capabilities; promo codes; the `Entitlements` port every slice reads (fail closed, inv-3); usage meters (meeting minutes per month with the lifetime tombstones of ADR 0007, model tokens per week by tier from F6 cost rows, token packs); hosted checkout and portal for three acquirers; auto-renewal and reconciliation; workspace seats per seat, monthly or yearly; company invoices with bank-statement matching (fr-15); refunds; sales inquiries; admin plans, promo and billing screens; referral and affiliate history (§8 SM-9).
- **Owns:** `subscriptions`, `subscription_segments`, `transactions`, `auto_charge_attempts`, `auto_renew_consents`, `card_bindings`, `recurring_payment_methods`, `premium_credit_ledger`, `usage_events`, `referral_rewards`, `affiliate_*`, `org_invoices`; platform (EU) `tariffs`, `promo_codes`, `payment_routes`. The exchange rate is F6's (ADR 0036).
- **Routes:** E webhooks; `/v1/billing/*`, `/v1/admin/{plans,promo-codes,billing}*`.
- **Depends on:** identity, F6 (cost settlement hook F6-C3, exchange rates, email receipts), workspaces (seat changes).
- **Emits:** `billing.payment_succeeded`, `.subscription_changed`, `.seats_changed`, `.quota_exhausted`.
- **Leo tools:** inside `account`: plan and usage (read).

#### 4. files
- **Scope:** files and folders of a person or a workspace; presigned multipart uploads (§10) used by every slice that takes bytes (recordings, Leo attachments, ticket attachments, hub materials, workspace uploads); download URLs (the missing open and download); the storage quota and `storage_used_bytes` (F-1); the "use with Leo" flags; transfer of a file to a workspace; deletion with Undo.
- **Owns:** `storage_files` (O1), `uploads`; the S08 key-layout ADR (DATA_MAPPING §6.2).
- **Routes:** no native or external; `/v1/files/*`, `/v1/me/uploads*`.
- **Depends on:** identity, workspaces (access), billing (`file_manager_gb`).
- **Emits:** `files.uploaded`, `.deleted`, `.leo_use_changed`.
- **Leo tools:** `files` toolset: search, read (digest), set "use with Leo" (W), move (W), delete (W, irreversible).

#### 5. meetings
- **Scope:** sessions and their lifecycle (start, end, silence sweep, inv-7), transcript storage keyed by `(session_id, seq)` (the WS drain writes through this slice's port), imports and audio uploads, the post-meeting pipeline (write-up, key points, decisions, action items, promises, risks, questions with evidence, mind map, per-minute index windows), templates and regeneration, folders, participants, the user's own notes synced with desktop, share links with comments and their public read API, export; Notes library and detail screens; the native meeting routes.
- **Owns:** `sessions`, `transcript_segments`, `meeting_speakers`, `meeting_notes`, `meeting_note_action_items` (until SM-3 moves them to tasks), `meeting_map_nodes`, `meeting_tags`, `session_tags`, `meeting_folders`, `meeting_templates`, `meeting_import_jobs`, `meeting_processing_runs`, `meeting_result_shares`, `meeting_share_comments`, `prompt_executions`, `meeting_workspace_impacts`; objects O3–O5; derived meeting windows in Qdrant.
- **Routes:** N per §3; `/v1/me/sessions/*`, `/v1/me/runs/{id}`, `POST /v1/me/sessions/{id}/end` (§10), `/v1/shared/{token}` (public).
- **Depends on:** files (uploads, audio), F6 (transcription, diarisation, models, cost), studio (prompt and model of the `notes` role), workspaces (access), billing (minutes), knowledge (index windows), memory (`record_recollections`), tasks (action items).
- **Emits:** `meetings.ended`, `meetings.notes_ready`, `meetings.deleted`.
- **Leo tools:** `meetings` toolset: search, get, read transcript, list decisions and action items (read); move to folder, regenerate notes, create or revoke a share link (W).

#### 6. capture
- **Scope:** the WS gateway role: live transcription with server `seq` and the durable Redis queue before display (inv-6, nfr-9), resume and gap replay, `transcription.busy`, `server.shutdown`, 1013 when full; in-meeting `ask`, `vision`, answers; the phone-to-Mac relay; simultaneous voice translation sessions; the desktop hotkey layout; ingest of LiveKit participant tracks (with rooms).
- **Owns:** hotkey layouts; Valkey resume state; the transcript queue (drained into meetings). F6 records live sessions as minute rows of `provider_costs`; the draft's `voice_sessions` and `translation_session` are folded into them (ADR 0041).
- **Routes:** N per §3. No `/v1/ws/voice` and no subtitles (web class, no consumer; §8 SM-8).
- **Depends on:** meetings (transcript port, start run on end), agent (`run_voice_turn` for answers), memory and studio (user context, role prompts and models), knowledge (live retrieval), F6 (realtime streams, minute cost rows), billing (entitlements, inv-13: no money ceiling stops capture), rooms (track egress).
- **Emits:** none of its own; meetings emits on end.
- **Leo tools:** none; it calls the agent port.

#### 7. knowledge
- **Scope:** sources (files, legacy notes per FM-2, connector sources, website crawl, the Obsidian vault, meeting transcripts), the parse → chunk → embed → index pipeline with status and re-index, Qdrant with the PostgreSQL keyword fallback, one search for every surface (`workspace.search`, live answers, the workspace and personal Leo scopes) with hits re-checked in PostgreSQL (inv-10, inv-14), knowledge quota (E-6), the Knowledge base screen.
- **Owns:** `knowledge_space`, `knowledge_source`, `knowledge_document` (+ `original_s3_key`, T-4), `knowledge_document_version`, `knowledge_node`, notes as knowledge items; derived `knowledge_chunk`, `knowledge_job`, the Qdrant collection.
- **Routes:** E vault; `/v1/knowledge/*`, `/v1/search`.
- **Depends on:** files (originals), connectors (grants and provider reads), workspaces (access payload), billing (`knowledge_base_mb`), F6 (embeddings, OCR, cost).
- **Emits:** `knowledge.indexed`, `knowledge.source_broken`.
- **Leo tools:** owns `workspace.search` of the core toolset; `knowledge` toolset: read a document, save a note (W, FM-2), sync a source (W).

#### 8. commitments
- **Scope:** people and organisations resolved from participants, speakers, attendees, senders and members (the one person reference for every slice); facts from meetings and their lifecycle — decisions with supersession, promises with owner and due date, open questions, risks; topics (threads) per container (a hub, a workspace) with stages, rounds, links and gaps; dismissals; due-date triggers instead of daily scans (ADR 0027); the decisions log read model of workspaces.
- **Owns:** `pcg_entities`, `pcg_edges`, `pcg_facts` (authoritative, nothing rebuilds them, T-2), topics, topic transitions, gap dismissals.
- **Routes:** no native or external; `/v1/people/*`, `/v1/decisions`, `/v1/topics/*`.
- **Depends on:** meetings (`notes_ready`, facts with evidence), hubs (filing → container), workspaces (visibility of decisions), mail (evidence that refutes a gap; later), F6 (models).
- **Emits:** `commitments.due`, `commitments.topic_looped`, `commitments.decision_superseded`.
- **Leo tools:** `people & commitments` toolset: find a person, open commitments, decisions (read); mark a topic done or abandoned, assign an owner (W).

#### 9. hubs
- **Scope:** hubs (personal containers per client, internal work or pipeline; ≤ 50), charter, archive, the kanban board a hub's work goes to, filing of meetings with suggestion and series memory, materials (links, uploads, meeting summaries, "gone" sources), the hub list summary, digest since the last meeting, feed, the cross-hub Today brief, meeting prep for the next 7 days, the once-a-day signal with quiet hours (through proactive).
- **Owns:** `hubs`, `hub_meetings` (filings), `hub_rules` (series memory), `hub_materials`.
- **Routes:** no native or external; `/v1/hubs/*`, `/v1/meetings/{id}/hub`, `/v1/brief/today`, `/v1/meetings/prep`.
- **Depends on:** commitments (topics and gaps per hub), meetings (titles, summaries, evidence links), calendar (series, upcoming events), tasks (boards; agreed tasks to the board), files (uploads), proactive (signal delivery).
- **Emits:** `hubs.meeting_filed`, `hubs.topic_looped` (consumed by proactive).
- **Leo tools:** `hubs` toolset: search, unresolved topics, digest (read); file a meeting (W).

#### 10. tasks
- **Scope:** one task store (§8 SM-3): personal and workspace tasks with title, status (todo, in progress, done), assignee (a person or a member), due date, priority, project, source (meeting, hub topic, mail, Jira); boards with columns, order and revision; the projection of workspace tasks onto a personal board; meeting action items as tasks; the home screen's "Today" as personal tasks due today; Jira boards in two-way sync with webhooks; the Kanban screen and the workspace Tasks screen.
- **Owns:** `tracker_projects` → boards, `tracker_statuses` → columns, `tracker_tasks`, `tracker_labels`, `tracker_task_labels`, `jira_links`, `jira_issue_links`; action items moved from meetings.
- **Routes:** E Jira; `/v1/tasks/*`, `/v1/boards/*`.
- **Depends on:** connectors (Jira grant, ADR 0002), workspaces (access, projects), commitments (people), F6.
- **Emits:** `tasks.assigned`, `tasks.due_changed`, `tasks.completed`.
- **Leo tools:** `tasks` toolset: search, list a board (read); create, update, complete, move (W).

#### 11. calendar
- **Scope:** calendars and events (CRUD, recurrence, focus blocks), two-way sync with Google, Microsoft and CalDAV through own OAuth (ADR 0002) and push channels, attendees, conference links, the iCal feed, upcoming events for meetings, hubs and workspaces, pre-meeting triggers for proactive.
- **Owns:** `calendar_integrations`, `calendar_events`, `calendar_event_moves`, `calendar_event_notifications`, `calendar_sync_state`, `external_event_mapping`, `calendar_watch_channels`.
- **Routes:** E per §3; `/v1/calendar/*`.
- **Depends on:** connectors (OAuth grants: `oauth_accounts`), commitments (attendees → people), meetings and rooms (link an event to a session or room).
- **Emits:** `calendar.event_changed`, `calendar.event_cancelled`.
- **Leo tools:** `calendar` toolset: search, find free time (read); create, update, cancel an event (W).

#### 12. mail
- **Scope:** mailboxes connected through connectors (Gmail, Outlook), the inbox screen (list, thread, flags, labels, archive, trash, drafts), Leo's insights per message (`decide(mail.triage)`, next step, reply-by, summary, draft), triage corrections as feedback, send and reply through the Action Gateway; storage per §8 SM-14.
- **Owns:** mailbox cursors and watches (`proactive_mail_cursors`, `proactive_mail_watches`), message index, insights, drafts.
- **Routes:** no native or external; `/v1/mail/*`.
- **Depends on:** connectors (grants, provider API), decisions (`mail.triage`), commitments (senders → people), agent (draft runs as background runs), F6.
- **Emits:** `mail.received` (signal for proactive), `mail.insight_ready`.
- **Leo tools:** `mail` toolset: search, read (read, untrusted text); draft, archive (W); send (W, irreversible, screen approval only).

#### 13. connectors
- **Scope:** the registry of connected services for every slice (Settings › Connectors; Knowledge › Sources and Kanban › Jira pick from it), Nango per home for Leo's connectors and knowledge sources, own OAuth grants for calendars and Jira (ADR 0002), token encryption in the home, revocation on disconnect and on account deletion, connection health (`connectors.broken`); provider read and act ports used by knowledge, mail and Leo.
- **Owns:** `connector_connections`, `oauth_accounts`, `meeting_integrations` (per §8 SM-11), the Nango schema per home.
- **Routes:** E integration OAuth callbacks per §3; `/v1/connectors/*`; the `/oauth/callback` cabinet page.
- **Depends on:** identity (deletion registry), F6.
- **Emits:** `connectors.connected`, `connectors.broken`, `connectors.revoked`.
- **Leo tools:** provider actions exposed through the owning slices (mail, calendar, tasks, knowledge); push a meeting result to Notion, Slack or a CRM (W, per §8 SM-11).

#### 14–18. Leo: agent, decisions, memory, proactive, errands
Scope, data and routes as the [Leo architecture](../design/leo/ARCHITECTURE.md) §3.3, §4, §10 and §13 define them, with three changes from this map:
- `models` is not a Leo slice: the model catalogue, defaults and role assignments go to `studio` (§8 SM-5); the agent reads them through studio's `ModelRoutes` contract.
- **agent** also owns the native model proxy (`/v1/ai/chat/stream`, `/v1/ai/vision/analyze`), the skills store used by Studio's skills dialog (`agent_skills`, `prompt_skills`), and the cabinet's Leo panel moved from NDJSON v1 to SSE v2 with action cards and the approvals inbox. Core toolset: `workspace.search` (knowledge), `read_result`, `load_toolset`, `navigate`, `ask_user`; egress `web` toolset.
- **memory** also owns Settings › Memory and `leo_personalization` (profile core). **proactive** owns `/v1/ws/user` and the Today feed the home screen shows. **errands** owns the two native reminder routes.
- **Leo is one per person** (§8.1 SM-1): it reads everything the person may access in Personal and in every workspace they belong to; the thread scope ranks its own space first and is the default target of writes; every answer names its sources and their space.

#### 19. studio
- **Scope:** the model catalogue and prices view (from F6), enable and default per model, role assignments; platform prompts (system prompt, behaviour, guardrails, feature prompts, versions, publish); the user's prompts per role, the active prompt per role and model settings per role; the user's personal context ("About you"); the Studio screen and the admin AI models and Platform prompts screens; the `PromptResolver` and `ModelRoutes` contracts used by capture, meetings, agent and memory.
- **Owns:** platform (EU) `models_registry`, `model_defaults`, platform `prompt_templates`; home `model_role_assignments`, user `prompt_templates`, `user_contexts`, `user_context_files` (L2 → object).
- **Routes:** no native or external; `/v1/studio/*`, `/v1/admin/{ai-models,platform-prompts}*`.
- **Depends on:** F6 (provider price sync, spend reports, OpenRouter credits), billing (models on the plan), agent (skills store).
- **Emits:** `studio.prompts_published`, `studio.model_disabled`.
- **Leo tools:** `studio` toolset: read the personal context (read); update it (W; a persistent-injection sink, never exposed over MCP).

#### 20. mcp
- **Scope:** Shosai as an MCP server with OAuth 2.1 (registry projection of Leo's tools, writes as `pending_approval`); MCP client connections for Leo (Settings › MCP) with sanitised tool descriptions.
- **Owns:** `mcp_client_connections`, `mcp_exposed_resources`, `mcp_oauth_clients`, `mcp_tokens`; platform `mcp_registered_clients`.
- **Routes:** E per §3; `/v1/mcp/*` settings.
- **Depends on:** agent (registry projection, Action Gateway), identity.
- **Leo tools:** external `mcp.<server>.<tool>`, egress or write.

#### 21. support
- **Scope:** operators talking to users. One ticket store for users and operators: tickets with category, messages, internal notes, attachments (through files), status, rating, assignee, priority, canned replies; the reply reaches the user through proactive and email. Newsletters (§8.1 SM-10): composing, audience, scheduling and sending admin mass email through F6's email port, which owns unsubscribe and suppression; the admin screen is designed in the new visual language before the newsletter step.
- **Owns:** `tickets` (the number sequence continues, U-7), `ticket_messages`, `ticket_attachments` (O8), canned replies; platform `broadcasts` (newsletters).
- **Routes:** no native or external; `/v1/support/*`, `/v1/admin/support/*`, `/v1/admin/newsletters/*`.
- **Depends on:** identity (operators), files, telemetry (a user's recent errors), billing (plan of the requester), F6 (email), proactive.
- **Emits:** `support.replied`, `support.resolved`.
- **Leo tools:** inside `account`: create a ticket (W), list my tickets (read).

#### 22. releases
- **Scope:** desktop builds per platform, channel and architecture; upload with SHA-256, publish, revoke, rollout percentage; the public latest endpoint for the download page and auto-updaters; download counters; the draft's download links.
- **Owns:** platform `app_builds` (L1 → `platform/app-builds/`).
- **Routes:** E download; `/v1/apps/latest`, `/v1/admin/apps/*`.
- **Depends on:** files (object storage), identity (operators).

#### 23. telemetry
- **Scope:** product events from web and native clients (`/v1/analytics/collect`), client errors and crashes grouped into issues with regressions and crash-free rate (`/v1/client/errors`, a public ingest path instead of `/admin/errors/ingest`), CSP reports, the admin Errors screens, the product-analytics tab of the dashboard; the satisfaction survey (§8.1 SM-10): when it is asked, the answers and their summary for operators; its user screen is designed in the new visual language before the survey step.
- **Owns:** `analytics_events`, `analytics_identity`, `client_errors`, issues, `satisfaction_surveys`; anonymous rows in the EU home.
- **Routes:** N and E per §3; `/v1/surveys/*`; `/v1/admin/errors*`, `/v1/admin/analytics*`, `/v1/admin/surveys*`.
- **Depends on:** identity, support (link to a ticket).

#### 24. rooms
- **Scope:** Shosai video rooms on LiveKit, recording, per-participant track egress to capture (fr-16), the room owner's meeting with company access, the join links already sent, the admin LiveKit screen; broadcasts and the room whiteboard (kept, §8.1 SM-8; their screens are designed in the new visual language before their steps). Subtitles and the room AI panel are dropped.
- **Owns:** `rooms`, `room_recordings` (O2, dual pointer with `storage_files`), `video_admin_actions`, `streams*`, `room_whiteboards`.
- **Routes:** E per §3; `/v1/rooms/*`, `/v1/admin/livekit/*`.
- **Depends on:** capture (track ingest), meetings (owner's meeting), files, workspaces, calendar (rooms of calendar events).

#### 25. site
Scope as S17 today ([ADR 0021](../adr/0021-public-site-on-nextjs-cabinet-on-vite.md), FM-1a, FM-1b), plus the public pages of shared links: the shared note `/s/{token}` with comments and the meeting result `/r/{token}`, served by the meetings API.

### 4.3 Frontend names

The mirror rule needs these renames, each made in the owning slice's first frontend step (URLs do not change):

| Cabinet feature today | Becomes | Note |
|---|---|---|
| `notes` | `meetings` | the recorded meetings |
| `meetings` | `meetings` (the overview page) | the overview becomes a page of `meetings` composing calendar and workspaces widgets |
| `file-manager` | `files` | |
| `knowledge-base` | `knowledge` | |
| `kanban` | `tasks` | |
| `workspace` | `workspaces` | its `ui/personal/*` widgets stay with their owners (shares → workspaces, tasks → tasks) |
| `leo` | `agent` | the visible name stays Leo (Leo architecture Q-5) |
| `upgrade` | `billing` | |
| `download` | `releases` | |
| `settings` | `settings` (dialog shell) | each section moves to its owner: account and privacy → identity, billing and usage → billing, Leo → agent, memory → memory, connectors → connectors, MCP → mcp, hotkeys → capture |
| `productivity` | `productivity` (composition) | no backend slice |
| `admin-*` | the owner's slice, `admin` sub-folder | e.g. `billing/admin/` |

---

## 5. Dependencies and build order

### 5.1 Dependency graph

```text
F1 (per the F1 audit) ── F6 ─────────────┐
                                        ▼
identity ── workspaces·core ── billing·entitlements ── files ── meetings ── capture
                                                         │         │
                                                         └── agent·core + Action Gateway
                                                                   │
        tasks ── connectors ── calendar ── knowledge ── commitments ── hubs ── decisions ── memory
                                                                   │
        workspaces·screens ── billing·payments ── proactive ── errands ── mail ── studio ── mcp
                                                                   │
        support ── releases ── telemetry ── rooms                  site (any time after F6)
                                                                   │
                                                          M1 ── M2
```

- **workspaces·core** is the first step group of `workspaces`: the access policy contract, `org_id` and `access` columns, `resource_grants`, RLS and the audit table. It comes before any slice with shareable resources, so meetings, files and knowledge are written against it from their first step instead of being retrofitted (nfr-15, inv-14). Its design waits for §8 SM-1.
- **billing·entitlements** is the first step group of `billing`: catalogue, the free plan, the `Entitlements` port and the minutes meter. Payments come later.
- F6 has no admin HTTP route (ADR 0041): `studio` and `identity` serve its reports and the kill switch from their own admin routers.
- `site` needs F1, F2 and F6 only and runs in parallel at any time.

### 5.2 Build order

| Wave | Goal for the user | Slices, in order | Exit |
|---|---|---|---|
| 1. Record, remember, ask | A person signs in on the web and on the desktop, records or uploads a meeting, reads its notes and asks Leo about it | identity → workspaces·core → billing·entitlements → files → meetings → capture → agent (core, Action Gateway) | the shipped desktop clients run end to end on v2 staging: sign-in, capture, upload, notes; Leo answers over meetings and files with SSE and approvals |
| 2. Track and connect | The home screen is real: tasks, calendar, recent notes, hubs that watch what is unresolved | tasks → connectors → calendar → knowledge → commitments → hubs; decisions and memory in parallel | action items are tasks on one board; meetings join calendar events; search and Leo cover knowledge; hubs fill themselves |
| 3. Team and initiative | Companies work together; Leo speaks first when it is worth it | workspaces (screens) → billing (payments, seats, invoices) → proactive → errands → mail → studio → mcp | invite, share, pay per seat; Today feed and reminders; the inbox triaged |
| 4. Operations and cutover readiness | Operators run the platform; every native and external route answers | support → releases → telemetry → rooms | the D1 gate passes and lists no native route as not served (`backend/tests/composition/native_routes_not_served.json` is empty; external routes are each slice's own design, F1 audit OD-2) |

- Within a wave, a later slice may start when the contracts it needs are published (§1 rule 3); the column order is the default for the backend path of `BACKEND-next-step.md`, which prefers the slice that unblocks the most others.
- In wave 2, `connectors` comes before `calendar` and `knowledge`, because both take their grants from it (cards 7 and 11); corrected when the map was applied.
- **telemetry** is small and its two native routes are fire-and-forget; it may be pulled into wave 1 when the desktop clients move to staging, so their crash reports are not lost.

---

## 6. Comparison with S01–S17

### 6.1 Slice by slice

| Old | Change | New |
|---|---|---|
| S01 Identity | kept; adds operator accounts and roles and the admin users screen; hotkeys move to capture; onboarding tour and interface font have no screen | identity |
| S02 Organizations | renamed to the product's word; adds teams, projects, share records, workspace knowledge items, usage, suspension; its core (access policy, RLS, audit) moves to the start of wave 1 | workspaces |
| S03 Billing | kept; adds token meters and packs, sales inquiries; referral and affiliate frozen (SM-9) | billing |
| S04 Meetings | kept; action items move to tasks (SM-3), hub assignment to hubs, the context-graph projection to commitments | meetings |
| S05 Realtime | renamed; subtitles and the web voice assistant dropped (no consumer); hotkeys added | capture |
| S06 Rooms | kept, last, mandatory; broadcasts and whiteboard kept; the room AI panel dropped (SM-8) | rooms |
| S07 Knowledge and search | **split**: indexing and search stay; the context graph becomes its own slice | knowledge, commitments |
| S08 Storage | renamed; becomes the one upload path for every slice | files |
| S09 Agent | five Leo slices kept as accepted; `models` merged into studio with prompts and personal context (SM-5) | agent, decisions, memory, proactive, studio |
| S10 MCP | kept; Settings › MCP is its client side | mcp |
| S11 Errands | kept | errands |
| S12 Connectors and calendar | **split** into three blades; Jira moves to tasks; meeting-result push per SM-11 | connectors, calendar, mail (new) |
| S13 Tracker | grows into the one task store with boards, workspace tasks, action items and Jira | tasks |
| S14 Analytics | errors and analytics merged as client telemetry; the satisfaction survey kept, with a new screen (SM-10) | telemetry |
| S15 Administration and support | admin screens go to their owners; support keeps one ticket store and the newsletters, with a new admin screen (SM-10); unsubscribe and suppression move to F6 | support |
| S16 Hub, downloads, remaining | **split**: hubs and releases; the top-bar ticker dropped (the cabinet calls the weather service from the browser); productivity is a composition screen | hubs, releases |
| S17 Public site | kept; adds the shared-note page `/s/{token}` | site |

### 6.2 New, merged, disappeared

- **New slices:** commitments, hubs, tasks, calendar, mail, studio (as a slice), telemetry (as a merge).
- **Merged:** three task lists → tasks; two connection screens → connectors; errors + analytics → telemetry; models + prompts + personal context → studio; user and admin support contracts → support.
- **Disappeared as capabilities:** subtitles, the web voice assistant WS, the room AI panel, the top-bar ticker backend (weather, holidays, stats), the onboarding tour, the admin profile and CRM templates, the own-OAuth meeting-result push apps (SM-11), referral and affiliate accrual (SM-9).
- **Kept although the new cabinet has no screen yet** (§8.1): broadcasts and the room whiteboard (rooms), the satisfaction survey (telemetry), newsletters (support). Each gets a screen in the new visual language before its frontend step.
- **Moved to foundation:** email unsubscribe and suppression → F6.

---

## 7. What the platform and the data mapping must change

### 7.1 F6

The F6 plan already provides the provider port, cost rows, spend control and per-user guards (the abuse guard until ADR 0041), email, periodic jobs and due rows, `decide`, `core/agent_tools` and the exchange rate. The new cut adds:

| Need | Why | F6 change |
|---|---|---|
| Unsubscribe and suppression list, `GET/POST /v1/unsubscribe`, `/email/{name}` images | E routes of S15 and S17; newsletters (kept, SM-10, in `support`) and transactional email both need suppression | email port gains a suppression list and the two routes |
| Spend reports per model: today, month, forecast, tokens, daily series; OpenRouter credits | the admin AI models screen (studio) | reports already planned in §3.6; add credits and the forecast; studio reads them |
| No admin HTTP route in F6 (ADR 0041, F6-D5; supersedes the trimmed step 10) | the new admin panel has no cost, abuse or kill-switch screen | F6's reports, one user's spend and the kill switch are services; studio's AI models screen and identity's account card serve them; a CLI engages the kill switch until then. Earlier text: keep guard and kill switch (FM-5), the abuse review API (used by identity's admin users screen for ban with refund); drop the unused cost timeline routes |
| Due-row sources from new owners | commitments (topic due dates), calendar (sync windows, pre-meeting triggers), knowledge (re-crawl), mail (cursor pulls), telemetry (rollups) | no change: `DueRowSource` covers them; none may scan all users (ADR 0027) |
| Consent flags in `CallContext` | nfr-14 | no change; identity and workspaces supply them |

### 7.2 DATA_MAPPING

DATA_MAPPING §5 is organised by S01–S17. In the follow-up step (§9) each table moves to its new owner as §4.2 lists, and the verifications without one owner get one:

| Verification | Owner in the new cut |
|---|---|
| E-2 minutes quota (sessions, `users` counters, `usage_events`) | billing, with meetings and identity providing their counts |
| T-4 knowledge documents without bytes | knowledge, with files and connectors |
| F-1 every pointer resolves; `storage_used_bytes` = Σ files | files |
| A-1 append-only audit across four tables | M1, each owner listed |
| O2 dual pointer of room recordings | rooms, with files |
| `meeting_note_action_items`, `tracker_*` | tasks (SM-3) |
| `hub*` | hubs; `pcg_*` → commitments |
| `models_registry`, `model_defaults`, `model_role_assignments`, `prompt_templates`, `prompt_skills`, `user_contexts`, `user_context_files` | studio (`prompt_skills`, `agent_skills` → agent) |
| `proactive_mail_cursors`, `proactive_mail_watches` | mail |
| `oauth_accounts`, `connector_connections`, `meeting_integrations` | connectors |
| `jira_links`, `jira_issue_links` | tasks |
| `satisfaction_surveys` → telemetry; `broadcasts` → support; `streams*`, `room_whiteboards` → rooms; `referral_rewards`, `affiliate_*` → billing as history (SM-8, SM-9, SM-10); `meeting_integrations` dropped (SM-11) |

---

## 8. Decisions for the owner

Each decision states the proposal first. "Blocks" names the first step that cannot start without it.

| ID | Question | Proposal | Trade-off | Blocks |
|---|---|---|---|---|
| **SM-1** | **The cabinet's workspace model contradicts the architecture.** The cabinet has one account with Personal and several workspaces, a switcher, sharing a personal recording into a workspace, teams, and audiences participants / team / workspace. ARCHITECTURE §6–§7 has a work account per company, separate from the personal account (two accounts per person), one company per work account, levels owner / selected / organization, no teams. | **Follow the cabinet and amend §6–§7 with an ADR:** one account per person in the home of their country; membership rows in the workspace's home reference the global user id; a workspace request opens its DB session in the workspace's home (resolved from an org directory, cached like the user directory); a personal item shared into a workspace of the same home is shared by reference, into another home it is copied after the owner confirms; teams become a grantee kind of `resource_grants`; participants map to `selected`; guest stays in the model without a screen; inv-15 reads "all data of a company lives in its home". | Fits the shipped design and lowers the user's load (one sign-in, one Leo across spaces). Costs a home lookup per workspace request, a cross-home copy flow, and a rewrite of §6–§7 and inv-15. The alternative keeps the architecture but forces two sign-ins, a switcher that switches accounts, and no direct share from Personal | workspaces·core (wave 1, step 2) |
| **SM-2** | Hubs and workspace projects are both containers of meetings, tasks and files. FM-1d left the hub's access in companies open | **Keep both now; hubs are personal only** (no sharing, as the cabinet shows); both run on the same topic engine in `commitments`, scoped by a container id, so a later merge (a hub inside a workspace = a project) keeps the data | One more concept for now; avoids redesigning two screens before either has users | hubs |
| **SM-3** | Three task lists and two checkbox systems | **One task store in `tasks`**: meeting action items are tasks from the first write; the home "Today" is personal tasks due today; workspace tasks are tasks with an org; kanban cards are tasks placed on a board | Frontend changes in kanban, productivity and notes; one migration path for `tracker_*` and action items; removes duplicate entry for the user | tasks; meetings writes action items through it from its pipeline step |
| **SM-4** | The home screen's year skyline with streaks (random data today) | **Drop it**; the home screen shows Today (tasks due, Leo's Today feed from proactive, the hub brief), the calendar and recent notes | Loses the home screen's visual centrepiece; removes a gamification surface and the heaviest new aggregation | productivity composition (wave 2) |
| **SM-5** | Studio's data has no owner in the Leo architecture: user prompts per role, personal context, role models, platform prompts | **A `studio` slice that absorbs the Leo `models` slice**: catalogue, defaults, role assignments, platform and user prompts, personal context; skills stay in `agent` | Amends Leo architecture §3.3; one owner for "how the AI behaves" instead of three | studio; meetings and capture use a default prompt and model until studio ships |
| **SM-6** | Memory in the cabinet is a model-written summary without a facts list; the Leo architecture requires list, edit, pin, forget, candidates and sources (L-5) | **Keep the summary as the face of Settings › Memory and add the facts page with sources**; the summary is derived from facts | More UI; without it L-5 and the "user can correct" promise do not hold | memory frontend step |
| **SM-7** | Sign-in screens do not exist in the new design | **Cabinet standalone routes outside the panels**: `/app/login`, `/app/register`, `/app/reset`, and `/app/connect` (already a native entry point); designed in the new visual language; the site links to them | Needs a design pass before identity's frontend step; keeps auth out of the Next.js site, which holds no logic | identity frontend step |
| **SM-8** | No user screen for rooms, broadcasts, whiteboard, the room AI panel or subtitles; only admin LiveKit and "Shosai room" as a meeting source | **Keep rooms (fr-16 is core) in wave 4 with a minimal join and room page; drop broadcasts, the whiteboard, the room AI panel and subtitles** (re-decides FM-1c); `/live/{token}` answers an "ended" page from the site | Loses fr-10 broadcasts (stretch) and reverses FM-1c; room links already sent keep working | rooms |
| **SM-9** | Referral and affiliate programmes have no screen; balances exist (DATA_MAPPING M-4) | **Freeze at cutover**: migrate rewards and balances as history, stop accrual, operators pay out remaining affiliate balances by hand | Users with referral links lose future rewards and must be told; no money is lost | billing |
| **SM-10** | Capabilities without any screen: satisfaction survey, newsletters, onboarding tour, top-bar ticker backend | **Drop all four**; unsubscribe and suppression move to F6 (§7.1); survey answers exported once, not migrated | Small visible losses in the draft that the new UI already dropped | M1 mapping |
| **SM-11** | Meeting-result push to Notion, Slack, HubSpot, Attio, Affinity, Zapier through own OAuth (FM-3) has no screen | **It becomes Leo and meeting actions over `connectors` (Nango), with approval; the own-OAuth integration apps retire; their callback paths redirect to Settings › Connectors.** Calendars and Jira keep own OAuth (FM-3 stands for them) | Users with push set up reconnect once; `meeting_integrations` is not migrated; one connection model instead of two | connectors |
| **SM-12** | The admin dashboard, users, roles and profile are templates; the frontend guards nothing in `/admin` | **Dashboard = platform overview composed from owners** (MRR and churn from billing, workspaces, AI spend, errors, LiveKit) **plus the telemetry tab; drop CRM, CRM v1 and the HR profile; users = identity's operator API (search, card, block, ban with refund); roles = a fixed set of operator roles (owner, support, finance, platform, releases, read-only) checked on every `/v1/admin/*` router; Leo in `/admin` gets no tools in this cut** | Template visuals replaced by real data, frontend work in each owner; no custom roles | identity (operators), each owner's admin step |
| **SM-13** | Two places to connect a source | **One registry**: Settings › Connectors connects; Knowledge › Sources and Kanban › Jira pick a connection and set its scope | Frontend change in two screens; one OAuth flow and one revoke path | connectors, knowledge |
| **SM-14** | Mail is a whole mailbox client in the UI | **Fetch-through over connectors**: store message metadata, Leo's insights and drafts in the home; read bodies from the provider on open; send through the provider API after approval; no own IMAP/SMTP server-side store | Depends on provider APIs and their quotas; keeps mail bodies out of Shosai's stores (less residency and deletion load) | mail |
| **SM-15** | Slice names that differ from §5 of the architecture | **Use the names of this map** (workspaces, capture, telemetry, studio, plus the new ones) and update §5 in the follow-up step | A rename across the architecture and plan documents; names say what each blade does | the follow-up step |

### 8.1 Decided by the owner on 2026-10-13

- **SM-1 — accepted, narrowed for launch.**
  - One account per person, in the home of their country; Personal plus workspaces, as the cabinet shows.
  - At launch a person joins only workspaces of their own home: invitations and domain joins across homes are refused with an explicit error. Cross-home membership, the profile copy it needs and cross-home sharing wait for the legal review (ARCHITECTURE §22); the data model leaves room for them (memberships reference the global user id).
  - **Leo is one per person** and sees everything the person has access to, in Personal and in every workspace they belong to. Every answer names its sources, including the space each one comes from. Access is checked on every read (§7); losing membership removes that workspace from Leo at once.
- **SM-3 — accepted.** Tasks have **one source of truth** in `tasks`. The kanban card, the home "Today" list, workspace tasks, a meeting's action items and a linked Jira issue are views of the same task; a change in any of them is the same change everywhere.

- **SM-2, SM-4, SM-5, SM-6, SM-7, SM-11, SM-12, SM-13, SM-14, SM-15 — accepted as proposed.**
- **SM-8 — changed.** Rooms are kept and are mandatory. **Broadcasts and the whiteboard are kept** (FM-1c stands for them). Subtitles and the room AI panel are dropped as proposed. Broadcasts and the whiteboard have no screen in the new cabinet yet: their screens are designed in the new visual language before the slice's frontend steps.
- **SM-9 — accepted.** The affiliate programme is removed; referral and affiliate accrual stop at cutover, rewards and balances migrate as history, remaining affiliate balances are paid out by hand.
- **SM-10 — changed.** **The satisfaction survey and newsletters are kept**; they need screens in the new design (the survey for users, newsletters in the admin panel). The onboarding tour and the top-bar ticker backend are dropped as proposed. Unsubscribe and suppression move to F6 as proposed and serve newsletters too.

Every decision of §8 is settled; §9 can run.

---

## 9. After approval

**Done on 2026-10-13**, after the owner approved this map and decided §8. Each item and where it landed:

1. Rewrite REWRITE_PLAN.md §3 Phase 2 (the slices of §4.1 with their scope in one line) and §4 (the graph and waves of §5); the launch line for slices takes the slice name: `Execute feature slice <name> from docs/plan/prompts/S-feature-slice.md.`, plans in `docs/plan/slices/<name>.md`. — done.
2. Replace the slice rows S01–S17 in STATUS.md with one row per slice of §4.1, with dependencies from §5.1. — done; the dependencies are the hard prerequisites of each slice's first step, later steps that wait for another slice are named in the notes.
3. Mark FEATURE_MAP.md as the draft's inventory: a reference, superseded as the plan of record by this map. — done.
4. Move DATA_MAPPING §5 tables to the new owners per §7.2, in the same commit (DATA_MAPPING §2: one mapping for M1). — done; `error_logs` went to F6 with the provider port, `meeting_integrations` became a drop (SM-11).
5. Update ARCHITECTURE.md §5 (domains) per SM-15, and §6–§7 per SM-1 if the owner takes the proposal; amend the Leo architecture §3.3 per SM-5. — done, with SM-1 as narrowed in §8.1 (also §1, §4.1, §8.1, §9 inv-15, §10, §19, §22) and the Leo scope rule of §11.2.
6. Update `prompts/S-feature-slice.md` (slice names instead of S01–S17) and the F6 plan per §7.1. — done.
7. Record the cut as an ADR (the next free number), with SM-1 as its own ADR if it amends the architecture. — done: [ADR 0038](../adr/0038-feature-slices-derived-from-the-product.md) (the cut), [ADR 0039](../adr/0039-one-account-per-person-with-workspaces.md) (SM-1).
