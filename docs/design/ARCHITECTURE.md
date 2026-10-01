# Whisperer v2 — Target Architecture

- **Status:** target state, fixed by the owner on 2026-09-30. Normative: where this document and an implementation disagree, the implementation is wrong or this document is updated first.
- **Diagram:** [architecture.html](architecture.html).
- **Scope:** B2C and B2B (small and mid-size companies, 5–200 seats) on one platform.
- **Placement:** one compute plane in the EU; two data homes — Russia and the EU.

---

## 1. Product scope

| id | Capability | Priority |
|---|---|---|
| fr-1 | Live meeting: audio capture, real-time transcription, in-meeting hints and answers | core |
| fr-2 | Post-meeting analysis: notes, decisions, tasks, map — also when the client never signalled the end | core |
| fr-3 | Workspace: meetings, notes, knowledge base, search, tracker, calendar, files | core |
| fr-4 | Leo: AI agent with tools; writing actions require confirmation | core |
| fr-5 | Payments: tariffs and credits, auto-renewal, three acquirers, reconciliation | core |
| fr-6 | Sign-in and sessions: password, social login, devices; one login for both data homes | core |
| fr-7 | Residency: data home chosen by country at registration; account transfer between homes | core |
| fr-8 | Export and full deletion of account data, including revocation of external grants | core |
| fr-9 | Voice assistant and simultaneous call translation | core |
| fr-10 | Video rooms and recordings (LiveKit), broadcasts, subtitles | stretch |
| fr-11 | Public site, help centre and blog in 16 languages | stretch |
| fr-12 | Company: creation, invitations by link and email, joining by verified email domain; roles owner, admin, member, guest | core |
| fr-13 | Access inside a company: meeting, note, folder and knowledge collection visible to the owner, selected members or the whole company; search and Leo see only what the user may see | core |
| fr-14 | Company administration: seats, members and roles, default access level, meeting retention, audit log, export and deletion of company data | core |
| fr-15 | Company billing per seat, monthly or yearly: invoice and closing documents for Russian legal entities; card or invoice for foreign companies | core |
| fr-16 | Server-side transcription of Whisperer video rooms per participant track; the speaker is known without diarization | core |
| fr-17 | Enterprise sign-in (SAML, OIDC) and SCIM provisioning | next step |

## 2. Non-functional targets

| id | Axis | Target |
|---|---|---|
| nfr-1 | Availability | 99.9% per month for sign-in, meeting capture and payment. Third-party AI outages are excluded and must degrade, not stop capture |
| nfr-2 | RPO | ≤ 5 min on database node loss; no acknowledged payment is lost on ordinary failover |
| nfr-3 | RTO | ≤ 1 h on server or database node loss; ≤ 4 h for data corruption or operator error (restore from backup) |
| nfr-4 | Residency | Primary data of Russian users and Russian companies stays in Russia, of others in the EU. Outside a home only the email HMAC, user id and home id exist. Derived copies (see §6) are an accepted exception |
| nfr-5 | Scale | 10 000 DAU, of which 3 000 company seats = 2 600 concurrent meetings; verified by calculation up to 100 000 DAU |
| nfr-6 | Live latency | Transcript line on screen p95 ≤ 2 s after the end of the phrase; platform share ≤ 300 ms |
| nfr-7 | API latency | Cabinet reads p95 ≤ 300 ms; platform overhead of a Leo turn ≤ 500 ms. Not met for Russian users by this placement (accepted, §20) |
| nfr-8 | Post-meeting | Notes ready p95 ≤ 10 min after the meeting ends |
| nfr-9 | Capture durability | A transcript line shown to the user survives process death |
| nfr-10 | Money | Zero double charges; the acquirer is acknowledged only after commit |
| nfr-11 | Cost and operations | ≤ 100 000 ₽/month infrastructure at the design point; one operator; Docker Compose and managed services |
| nfr-12 | Migration | Maintenance window ≤ 30 min at night; shipped desktop and mobile clients keep working without an update |
| nfr-13 | Deletion | Account deletion removes data from every store and revokes external grants |
| nfr-14 | Cross-border | Audio and text of Russian users and companies reach foreign AI providers only with consent (user, or company as data operator); a transit node stores nothing |
| nfr-15 | Company isolation | No API response, search result or Leo answer contains data of another company or a resource the user has no access to |
| nfr-16 | Member removal | A removed member's sessions are revoked within 1 min; content they created stays with the company |
| nfr-17 | Audit | Every administrative action and access change is recorded; retention 12 months |
| nfr-18 | Company onboarding | Company creation, invitations and card payment are self-service; invoice payment is confirmed by the next business day |

## 3. Design point

| Quantity | Value | Derivation |
|---|---|---|
| Users | 10 000 DAU: 7 000 B2C, 3 000 company seats (~100 companies × 30) | owner |
| Home split | 80% Russian home, 20% EU home | assumption |
| Recording | B2C 60 min/day, company seat 120 min/day → 780 000 min/day, 19 500 meetings/day | assumption |
| Concurrent meetings | 2 600 peak (2 080 RU / 520 EU) | 780 000 ÷ 600-min window × 2 peak |
| WebSockets | ≈ 8 700 peak | 2 600 × 2.2 + 3 000 open cabinets |
| WS processes | 11 under load, 13 with reserve | 250 meetings per process (to be measured) |
| Audio | 2.0 Gbit/s in, 2.66 Gbit/s to providers; 99 TB in / 132 TB out per month | PCM16 24 kHz × 2 channels; base64 × 4/3 |
| Transcript writes | 289 lines/s peak | 400 lines per meeting-hour |
| Transcript storage | 5.2 M rows/day; ≈ 1.9 TB/year | ≈ 1 KB per row with indexes |
| Meeting vectors | 0.78 M windows/day; 437 GB/year | one window per minute, 512-dim halfvec |
| Post-meeting runs | 5 850 in the peak hour; 292 in flight | 30% of meetings end in the peak hour; 180 s per run |
| HTTP | 2.0 M/day; 116/s peak | 200 requests per user per day, peak × 5 |
| DB time per request | 180 ms for Russian users (4 × 45 ms), 4 ms for EU users | round trip plane → RU DB 45 ms |
| Held DB connections | ≈ 17 for RU cabinet reads; ≈ 4 for transcript batches | 116/s × 80% × 0.18 s; 13 × 2 batches/s × 3 × 45 ms |
| Events | ≈ 6–7/s peak | ≈ 4 events per meeting |
| Audit log | ≈ 20 000 events and 20 MB/day; 7 GB/year | 100 companies × 200 actions |
| Speech-to-text cost | $2 340–4 680/day; per company seat $7.92–15.84/month | $0.003 per audio minute, 1–2 channels |
| Restore time | 300 GB ≈ 0.8 h; 1 TB ≈ 2.8 h | 100 MB/s |
| Availability for Russian users | plane availability × availability of the plane → RU DB link | e.g. 0.999 × 0.9995 = 99.85% |

## 4. Topology

### 4.1 Placement rules

1. All application processes run as **one deployment in the EU** (the compute plane), next to the AI providers. AI providers are not reachable from Russian addresses.
2. Data lives in **two homes**. Each home = one managed PostgreSQL cluster (primary + standby, WAL archive, PITR) behind PgBouncer + one S3 bucket.
   - Russian home: St Petersburg, 45 ms from the plane.
   - EU home: Netherlands, < 2 ms from the plane. It also holds the directory and the data without an owning account (§6).
3. A request opens its database session **in the home named by the access token** (user home, or the company's home for a work account). Workers take the home from the task payload.
4. No cross-home writes. A user or company belongs to exactly one home.

### 4.2 Components

| Component | Where | Responsibility | Scaling |
|---|---|---|---|
| Clients | user devices | Web cabinet (SPA, PWA); macOS, iOS, Linux, Windows apps; external MCP clients. One base URL `whisperer.one`. Desktop clients buffer up to 30 s of unsent audio | — |
| Edge | plane | NGINX ×2: TLS, static assets, rate limits; `/v1/ws/*` → WS gateway (least_conn), everything else → API; handshake closed with 1013 when the plane is full | 2 nodes |
| API | plane | FastAPI: cabinet, Leo, billing, companies and access policy, administration, presigned uploads, acquirer webhooks | N processes; one pool per database |
| WS gateway | plane | Live capture, voice, translation, subtitles, ingest of room participant tracks from LiveKit egress. Meeting resume state lives in Redis; any process can resume any meeting | 250 meetings per process; 11–13 processes |
| Workers | plane | TaskIQ on Redis Streams, queues `critical`, `default`, `bulk`, `meeting`: outbox relay, transcript queue drain, post-meeting pipeline, indexing, bank statement reconciliation | processes per queue; one pool per database |
| Scheduler | plane | One process: periodic jobs from `schedule_runs`, due rows from `errands`. Only enqueues tasks | 1 |
| Valkey (managed) | EU | Task streams, transcript queue, locks, WS slots, meeting resume state, Leo checkpoints, circuit-breaker state. AOF every second, replica, `noeviction` | managed |
| Redis cache | plane | LRU cache only; losing it is harmless | container |
| Qdrant | plane | Vector index: knowledge chunks and per-minute meeting windows. Payload: tenant, owner, access level, grantees. Derived; rebuilt from sources | 1 node |
| LiveKit | plane | SFU, egress (room recording, per-participant audio tracks to the WS gateway), coturn | pinned versions |
| Nango | plane | OAuth proxy for connectors; one instance per home, state in its home database | pinned versions |
| PostgreSQL RU | Russia | Source of truth of the Russian home | managed, PgBouncer |
| PostgreSQL EU | EU | Source of truth of the EU home; directory tables; platform tables and telemetry without an account (§6) | managed, PgBouncer |
| S3 RU, S3 EU | per home | Files, recordings, exports, knowledge sources; lifecycle rules | — |
| AI providers | external | OpenRouter, OpenAI Realtime, Google Gemini Live, Deepgram, pyannote, Mistral OCR — reached directly from the plane | quotas per contract |
| Payments | external | TBank, CloudPayments, lava.top (cards); bank statement API (invoices) | — |
| Observability | plane + outside | Grafana stack: Prometheus (metrics), Loki (logs), Tempo (traces), Grafana (one pane); OpenTelemetry Collector; Alertmanager (Telegram); node exporter; uptime probes run outside the plane | single nodes, local disks with size caps |
| Delivery | GitHub | GitHub Actions builds the image from a green commit into a registry; `scripts/release.sh` deploys to staging, then to the plane | — |

### 4.3 Connections

| From → To | Kind | Deadline | Retry owner | Bound |
|---|---|---|---|---|
| Clients → Edge | HTTPS, WSS | handshake 5 s | client, reconnect with jitter | 50 req/s and 1 000 connections per IP |
| Edge → API | HTTP | connect 2 s; response 30 s | edge, one retry for idempotent methods | 64 requests in flight per process |
| Edge → WS gateway | WSS, least_conn | handshake 5 s | client | 250 meetings per process; full → 1013 |
| Clients → LiveKit | WebRTC | connect 10 s | LiveKit client | 16 participants per room |
| LiveKit egress → WS gateway | participant audio track (PCM over WSS) | connect 5 s; lives while the participant is in the room | egress reconnects; on failure the room is recorded whole and analysed after the meeting | one track per speaker, 16 per room |
| WS gateway → AI | audio stream | connect 3 s; phrase max(15 s, 2 × duration) | WS gateway, one reconnect | provider session pool below the provider quota; over → `retry_later` |
| WS gateway → Valkey | transcript queue, resume state | 20 ms | none; without Redis the line is shown marked "not saved" and written to the DB directly | queue bounded by meeting length |
| WS gateway → PostgreSQL (home) | transcript batch | 500 ms per batch | queue drain worker, keyed by (session_id, seq) | one batch in flight per process |
| API → PostgreSQL (home) | SQL via PgBouncer | pool wait 2 s; statement 10 s | none for writes; one retry for reads | pool 10 per process per database |
| API → directory | SQL (EU home) | 300 ms; cached 60 s | none; cache on failure | sign-in, registration, transfer, deletion only |
| API → Valkey | enqueue | 50 ms | outbox for money and email; 503 otherwise | stream ≤ 500 000; alert at depth 500 |
| Scheduler → Valkey | ticks | 50 ms | next tick | one tick per job in flight |
| Valkey → Workers | task stream | task deadline; lease 120 s with extension | broker: 5 deliveries, then dead-letter with alert | provider semaphore: 292 runs in flight |
| Workers → PostgreSQL (home) | SQL | statement 60 s | sweep of unfinished runs; ≤ 3 attempts per stage on every path | pool 5 per process per database |
| API, Workers → AI | chat, Leo, search, analysis | connect 10 s; stream stall 45 s; 120 s per analysis call | one retry before the first byte; breaker per call kind; stage ≤ 3 attempts with effect key | provider-wide semaphore in Redis; retry budget 20% |
| API, Workers → Qdrant | search, indexing | search 2 s; write 60 s | search: none (fallback to PostgreSQL keyword search); indexing: cursor sweep | 32 queries per process, 4 per tenant |
| Clients → S3 (home) | presigned upload and download | signature valid 15 min | client | size limit in the signature |
| API → Payments | checkout, charge | 20 s, outside any transaction | reconciliation every minute by order id | intent committed before the call |
| Payments → Edge | webhook | answer within 5 s, after commit | acquirer | row lock wait 5 s |
| Workers → bank | statement | 30 s | next hourly pass | one day of payments |
| Monitoring → Edge | uptime probe | 10 s | next probe | — |

## 5. Process model and code structure

- **One modular monolith, one image**, four process roles: `api`, `ws`, `workers` (per queue), `scheduler`.
- **Feature First** (vertical slices): `core/`, `features/<domain>/`, `composition/`, `entrypoints/`. A feature owns its data, application services, channels (HTTP, WS, tasks, consumers) and its README.
- A feature depends on another only through its `contracts`. Boundaries are enforced by import-linter contracts in CI.
- Domains this design places responsibilities on:
  - `identity` — accounts, sessions, directory, home routing;
  - `organizations` — companies, memberships, roles, seats, access policy, audit;
  - `billing` — tariffs, subscriptions, acquirers, company invoices;
  - `meetings` and `realtime` — capture, transcript, pipeline;
  - `rooms` — LiveKit rooms, recording, track ingest;
  - `knowledge` — sources, indexing, search;
  - `agent` — Leo;
  - `errands` — delayed Leo actions;
  - `connectors` — Nango;
  - `analytics`, `alerting`.

## 6. Data placement and residency

- **Home of an entity:**
  - personal account → home chosen by country at registration;
  - company → home fixed by contract;
  - work account → home of its company;
  - account migrated from the draft → Russian home; it moves to the EU home by account transfer once the person confirms a country outside Russia ([ADR 0004](../adr/0004-migrated-accounts-start-in-russian-home.md)).
  A person with a personal and a work space has two accounts.
- **Directory** (EU home): `email_hmac`, `user_id`, `home`, `state`, `version`. `directory_domains` maps a verified company email domain to the company and its home. No other personal data outside a home.
- **Data without an owning account** (EU home, one copy, one writer; [ADR 0005](../adr/0005-data-without-owner-in-eu-home.md)):
  - platform tables: tariffs, promo codes, payment routes, exchange rates, the model registry and defaults, platform prompts and notes, MCP client registrations, admin mailings, provider error logs, desktop builds;
  - home tables reference them by id without a foreign key; a platform id is retired, never deleted;
  - telemetry without an account (product events before registration, anonymous client error reports), subject to the legal review in §22.
- **Home routing:**
  - sign-in finds the home by `HMAC(email)`, checks the password in that home and issues a token that carries the home;
  - later requests use the token and do not consult the directory;
  - processes cache directory entries for 60 s;
  - account transfer bumps `token_version`.
- **Derived copies in the EU — accepted exception to nfr-4:** meeting resume state, Leo checkpoints (Redis), task payloads, vector index points of Russian users and companies. Retention ≤ 24 h in Redis; index points live as long as their source.
- **Cross-border AI:**
  - personal user — consent in the product;
  - company — consent in the contract as data operator; Whisperer processes on its behalf.
- **Account transfer between homes:** a saga with a step journal (`home_transfers`): freeze writes → export by the table registry → import → verify manifest → switch directory → bump token version → purge source. Each step is idempotent; purge is last.

## 7. Tenancy and access control

- **Owner of a resource:**
  - personal resources — `user_id`, `org_id` empty;
  - company resources — `org_id` plus an access level: `owner | selected | organization`;
  - selected members — rows in `resource_grants`.
- Resources with company access: meetings, notes, folders, knowledge collections.
- The public link visibility (`private | shared | public`) is independent of company access: a private link does not resolve, a shared link hides the title in previews and may carry a password, a public link shows the title.
- **One access policy** (feature `organizations`) decides every read and write. Domains call it; they never compare owners themselves. The access check runs in the same query that reads the resource.
- **Access rights are never cached.** Content may be cached; the right to see it is checked on every access.
- **Row-level security** is the second line:
  - each transaction starts with `SET LOCAL app.org_id` (and `app.user_id`);
  - policies on company-scoped tables reject foreign rows;
  - migrations and sweeps use a dedicated role.
- **Search and Leo:**
  - Qdrant filters by tenant (`o_<id>` or `u_<id>`) and by the requester's access;
  - every hit is re-checked against PostgreSQL before it is returned, because index payload lags access changes by seconds.
- **Roles:**
  - owner — everything, including billing and deletion;
  - admin — members, seats, settings, audit;
  - member — own and shared resources;
  - guest — only explicitly granted resources.
  The last owner cannot leave.
- **Joining:** invitation token, or a verified email domain (DNS TXT). A join above paid seats returns 402 and notifies the admins.
- **Member removal:** membership → `removed`, `token_version` bumped (sessions die within 1 min), created content stays with the company, ownership transferred to an admin.
- **Audit:** every administrative action and access change writes `org_audit_events` in the same transaction. The application role has no UPDATE or DELETE on that table.
- **Enterprise sign-in** (SAML, OIDC, SCIM): not built now. The data model leaves room for a per-company identity provider.

## 8. Data model

### 8.1 Entities

| Entity | Representation | Identity | Ordering authority | Conflict rule | Durability point | Retention |
|---|---|---|---|---|---|---|
| Account | `users` in its home | UUID, global | home primary | all writes go to one home; writes frozen during transfer | commit before response | anonymised on deletion; directory row kept 30 days |
| Directory entry | `directory_entries` in the EU home | `email_hmac` PK; `user_id` unique | EU primary | unique index: first registration wins | commit | 30 days after deletion |
| Company | `organizations` | UUID | company home; seats and plan under a row lock | one writer | commit + audit event | after contract end and export, deletion saga |
| Membership | `memberships` | (org_id, user_id); a work account has one company | company home | only admins change roles; last owner stays | commit + audit event; removal bumps token version | row kept as `removed` |
| Access | `org_id`, `access` columns + `resource_grants` | (resource type, resource id, member id) | company home | last write wins; revocation immediate | commit + audit; index updated via outbox | with the resource |
| Payment | `transactions`, `auto_charge_attempts`; outbox in the same transaction | UUID; acquirer order id; period key `subscription:date` | home: transaction row and subscription row locks | webhook replay stops at the lock and status | commit before acquirer ack and before the charge call; unknown outcome stays `charging` until reconciliation | never deleted |
| Company invoice | `org_invoices`; PDF in the home bucket | invoice number from a home sequence | company home | payment matched once by invoice number; unmatched → operator queue | payment, seats and audit in one transaction | never deleted |
| Transcript line | `transcript_segments`, monthly partitions | (session_id, seq); seq assigned by the server at phrase intake; `started_at` = phrase start | the WS process leading the meeting | replay of (session_id, seq) ignored; equal text is not a conflict | Redis transcript queue (AOF) before the frame is sent; home DB in 500 ms batches, `ON CONFLICT DO NOTHING` | with the meeting; partitions > 12 months exported to S3 |
| Pipeline run | `meeting_processing_runs`, stage state in JSONB | UUID; idempotency (session_id, source) | home DB; stage executed by the message lease holder | finished stages skipped; results upserted by natural keys | stage commit; the queue may be lost, the sweep restores from DB | with the meeting; audio ≤ 72 h |
| Cost | `provider_costs` (monthly partitions), credit ledger | UUID + effect key (run:stage:call or request id) | home DB; subscription row lock on debit | same effect key → no second row or debit | written by the provider port with the call result; live capture batched every minute | never deleted; partitions > 24 months dropped |
| Vector | Qdrant point | UUIDv5(source, window, build) | none — derived | overwrite by point id; tenant and access from request scope | commit of the source | with the source; full rebuild by cursor |
| File | S3 object + `storage_files` | UUID; key prefixed by owner (objects migrated from the draft keep their keys, [ADR 0006](../adr/0006-draft-bucket-becomes-russian-home-bucket.md)) | home DB: pointer after upload completes | objects immutable | multipart complete, then pointer commit | row, then object; orphans by lifecycle rules |
| Leo state | checkpoints in Redis, TTL 24 h | thread `user_id:session_id` | Redis; writing action guarded by a one-time key | last checkpoint wins | Redis AOF; loss restarts the dialogue | TTL |
| Errand and schedule | `errands`, `schedule_runs` in the home DB | UUID; job name | `FOR UPDATE SKIP LOCKED`; the scheduler walks both homes | errand runs only from `scheduled`; a job runs only if `last_run_at` is older than its interval | commit | finished errands after 24 h |
| Event | `outbox_messages`, `processed_events` | event UUID = dedup key; (consumer, event_id) unique | home DB | per-subscriber task; mark in the subscriber's transaction | commit with the effect | published rows after 7 days |
| Audit event | `org_audit_events`, monthly partitions | UUIDv7 | commit order | append-only | same transaction as the action | 12 months, longer by contract |

### 8.2 Rules

- Consistency follows the invariant:
  - money, rights, directory — strict, fail closed;
  - capture — availability first, lines go to the queue;
  - search and analytics — derived, may lag.
- No cross-home write conflicts by construction.
- High-volume tables:
  - UUIDv7 keys and monthly partitions: `transcript_segments`, `provider_costs`, `prompt_executions`, `usage_events`, `login_events`, `error_logs`, `client_errors`, `agent_audit`, `org_audit_events`;
  - retention by dropping partitions, except `usage_events`: its tombstones count toward the lifetime Free quota and live as long as the account ([ADR 0007](../adr/0007-usage-tombstones-kept-for-lifetime-quota.md)).
- Every store is declared authoritative (with acknowledgement point, RPO, RTO) or derived (with source and cursor).
- Derived stores are rebuildable:
  - Qdrant — cursor `sessions.indexed_upto_seq` + build version;
  - context-graph projection — must not overwrite user decisions stored on facts.

## 9. Invariants

| id | Invariant |
|---|---|
| inv-1 | An account has exactly one home; an email is unique across homes |
| inv-2 | Outside its home, primary data exists only as email HMAC, user id and home id; derived copies per §6 |
| inv-3 | Entitlements fail closed; a paid period is never lost under concurrent confirmations |
| inv-4 | One charge per order and per renewal period; the acquirer is acknowledged only after the record is durable |
| inv-5 | Every grant (period, credits, reward) follows from exactly one successful transaction |
| inv-6 | A transcript line shown to the user is stored or recoverable; order inside a meeting is assigned by the server |
| inv-7 | A meeting that ended without an explicit end still reaches processing |
| inv-8 | A pipeline stage counts once; a retry creates no duplicate results |
| inv-9 | One external model call produces one cost row and at most one credit debit |
| inv-10 | A vector index is derived and rebuildable; a query never returns data the requester may not see |
| inv-11 | Bytes live only in the owner's home; the storage quota is not exceeded |
| inv-12 | A writing agent action runs at most once and only after confirmation |
| inv-13 | No money ceiling stops a meeting or standard transcription (unlimited-meetings promise) |
| inv-14 | A company resource opens only for its members at the resource's access level; checked on every access, never cached; search and Leo obey the same rule |
| inv-15 | All data of a company and the work accounts of its members live in the company's home |
| inv-16 | Active members ≤ paid seats |
| inv-17 | An administrative action or access change does not happen without an audit event in the same transaction |

## 10. Interfaces

| Interface | Transport | Idempotency | Deadline | Caller-visible result |
|---|---|---|---|---|
| Sign in | `POST /v1/auth/login`; directory lookup by HMAC(email) | lookup is a read | 300 ms directory + home check (4 × 45 ms for RU) | token with home; directory down → sign-in by cache, registration 503 |
| Live capture | `WSS /v1/ws/realtime`: audio frames → `transcript {seq, text, speaker}`; `hello` carries a protocol version | (session_id, seq); on reconnect the client sends the last seq and receives the gap | line on screen ≤ 2 s | `transcript` = queued durably; `transcription.busy` instead of silent drop; ≤ 3 recognitions in flight per connection; full plane → 1013; `server.shutdown` before deploy |
| End meeting | `POST /v1/me/sessions/{id}/end` → 202 `{run_id}`; `GET /v1/me/runs/{run_id}` | (session_id, source) returns the same run | 300 ms; notes p95 ≤ 10 min | PENDING → SUCCEEDED, PARTIALLY_COMPLETED or FAILED; silent meetings closed after 5 min of silence |
| Acquirer webhook | `POST /v1/billing/webhook/{provider}` | `external_id` unique | answer within 5 s, after commit | 2xx only after commit; 5xx → acquirer retries; reconciliation every minute |
| Upload | `POST /v1/me/uploads` → presigned part URLs; PUT to S3; `POST …/complete` | upload id; part replay overwrites | 300 ms for URLs; 15-min signature | READY with run id; REJECTED over size; abandoned uploads removed by lifecycle after 24 h |
| Invite and join | `POST /v1/orgs/{id}/invites`; `POST /v1/orgs/join {token}`; domain join at registration | one-time token; repeat returns the same membership | 300 ms | membership; 402 no seats; 409 address already in another company |
| Share inside a company | `PUT /v1/{resource}/{id}/access {level, members[]}` | set-state | 300 ms | new access + audit event; 403 without right; revocation immediate |
| Company invoice | `POST /v1/orgs/{id}/invoices {seats, period, payer}` → number + PDF | invoice number; statement payment matched once | 2 s; seats active by the next business day | `paid`, `issued` or unmatched payment → operator alert after 24 h |
| Room transcription | LiveKit track egress → WSS to the WS gateway, one participant per stream | (session_id, seq) | line on screen ≤ 2 s | transcript per participant in the room owner's meeting with company access; egress failure → whole-room recording analysed after the meeting |
| Account transfer | internal `POST /internal/transfers {user_id, to_home}`; saga steps as tasks | transfer id; each step checks journal and manifest | minutes per user | SUCCEEDED after manifest check and source purge; CANCELLED before the directory switch; RECONCILING if the target did not confirm |

**API contract rules:**
- OpenAPI 3.x is the contract between backend, web and native clients.
- Changes are additive only; unknown fields and frame types are ignored by clients.
- Collections use cursor pagination with a maximum page size. This includes meeting transcript, map and model executions.
- One error envelope everywhere.
- A snapshot test covers public routes and the full set of WebSocket frame types.

## 11. Critical flows

1. **Live meeting.**
   1. Client → Edge → least-loaded WS process.
   2. WS → AI: audio → text.
   3. WS assigns `seq` and appends the line to the Redis transcript queue (AOF).
   4. The frame is sent to the client.
   5. The line is drained to the user's or company's home DB in a batch within 500 ms.
2. **Room transcription.**
   1. Participants → LiveKit (WebRTC).
   2. Egress streams each participant's audio track to the WS gateway.
   3. The rest is the same as the live meeting; the speaker is the track's participant.
   4. The transcript is saved in the room owner's meeting with company access.
3. **Post-meeting analysis.**
   1. End command, or the silence sweep after 5 min.
   2. Run row committed; stage task enqueued.
   3. The worker executes the stage under a lease: AI call with effect key, results upserted, cost row written by the provider port.
   4. Next stage enqueued.
   5. Notes committed; index windows written to Qdrant by cursor.
4. **Sign in.**
   1. Client → Edge → API → directory `HMAC(email)` → home.
   2. Password checked in the home.
   3. Token issued with the home.
5. **Open a colleague's meeting.**
   1. API: `SET LOCAL` company and user.
   2. One query reads the meeting and checks its access level; RLS applies.
   3. Search: Qdrant filter by tenant and access, then hits re-checked in PostgreSQL.
6. **Card payment.**
   1. API commits a pending transaction.
   2. Acquirer called outside the transaction.
   3. Webhook: lock the transaction row → mark success → extend the subscription under its row lock → outbox (receipt email, rewards) → commit → answer 2xx.
7. **Invoice payment.**
   1. API commits the invoice and stores the PDF in the home bucket.
   2. Hourly worker reads the bank statement and matches by invoice number.
   3. One transaction: invoice paid + seats extended + audit event.
8. **Link to the Russian DB lost.**
   - Russian users get 503 on cabinet, payment and Leo; EU users are unaffected.
   - Live meetings continue; lines accumulate in the Redis queue and drain after recovery.
   - Alert from the external probe.

## 12. Async work and scheduling

- **TaskIQ on Redis Streams.** Queues: `critical` (money, email), `default`, `bulk`, `meeting`. Every task declares a deadline, queue and retry policy.
- **Events:**
  - written as `outbox_messages` in the transaction of the effect;
  - the relay enqueues one task per subscriber;
  - the subscriber writes `processed_events (consumer, event_id)` in its own transaction, so redelivery is harmless;
  - events carry no personal data.
- **Delayed actions (errands):** a row with `run_at`; the scheduler enqueues due rows (`FOR UPDATE SKIP LOCKED`) and records the run.
- **Periodic jobs:** `schedule_runs.last_run_at`. A missed interval runs once on start, not as a backlog.
- **Provider-wide concurrency:** a semaphore in Redis per provider, not per process.
- **Revisit triggers:**

| Mechanism | Revisit when |
|---|---|
| Event delivery through the outbox and TaskIQ | a consumer outside the application process; or sustained > 20 events/s (relay limit at batch 100 per 5 s); or a new consumer needs history older than 7 days |
| Delayed actions as `errands` rows | a scenario with three or more steps that waits for external events with compensations |

## 13. Resilience

### 13.1 Single points of failure

- The compute plane is shared by both jurisdictions; processes inside it are duplicated.
- The link plane → Russian DB; losing it stops Russian users.
- Managed Valkey (with replica): task streams, transcript queue, meeting state.
- EU DB as directory primary: registration and transfer depend on it.
- The access policy: one module for all checks, covered by isolation tests on every read path and by RLS.
- One operator.

### 13.2 Degradation

| Failure | Behaviour |
|---|---|
| Link to the Russian DB lost | Russian users: 503 on cabinet, payment, Leo. Live meetings continue; the queue drains after recovery. EU users unaffected |
| A home DB slow | Held connections grow in that home's pool only |
| AI provider slow or down | Breaker opens; retries within a 20% budget; the meeting continues without recognition, marked in the UI |
| Plane full | Handshake 1013; clients retry with jitter |
| Directory unavailable | Sign-in by cache, running sessions by token, registration and transfer 503 |
| Redis unavailable | Capture continues; lines are shown marked "not saved" and written to the DB directly; expensive AI operations fail closed (kill switch treated as engaged); unlimited meetings unaffected |
| LiveKit egress down | Room recorded whole and analysed after the meeting |
| Bank API down | Invoices issued; crediting waits for the next pass; seats stay active until the end of the paid period + 7 days |
| Index lags an access change | Hits re-checked against the DB; revoked content is not returned |

### 13.3 Recovery

- DB node loss → standby promotion ≤ 15 min.
- Loss of both nodes → PITR ≤ 4 h. The 1-hour target (nfr-3) covers one node.
- Quarterly restore drill of each home into an isolated instance, with invariant checks and the achieved RPO and RTO recorded.
- Qdrant full rebuild every six months from sources.
- Redis loss → the last second of the transcript queue is lost. The pipeline is restored by the sweep from the DB; events and email are restored from the outbox.
- The plane is stateless: redeploy the previous image from the registry.
- Account transfer is reversed by the same saga.

### 13.4 What breaks first

1. Connections and latency to the Russian DB (180 ms DB time per Russian request).
2. The provider quota for concurrent recognition sessions.
3. Audio bandwidth of the plane at the top of the hour.

### 13.5 Capacity rules

- WS and worker process counts are configuration: reserve N+2, review at 70% of the per-process limit.
- Revisit the capacity model when the peak exceeds configured capacity more than once a month, or more than 20 WS processes are needed (≈ 5 000 concurrent meetings, ≈ 19 000 DAU).
- Sharding a home DB: not before 100 000 DAU or a primary DB above 300 GB after moving vectors out.

## 14. Engineering rules

1. **Database sessions:**
   - the session commits before the HTTP response is sent;
   - no external call (AI, acquirer, S3) inside an open transaction.
2. **Connection pools:**
   - exactly one pool per process per database;
   - the sum of pools of all processes, including release overlap, stays under the server limit through PgBouncer.
3. **Money:**
   - acknowledge after commit;
   - period changes only through one function that locks the subscription row (`FOR UPDATE` with `populate_existing`);
   - side effects through the outbox.
4. **Cost:** every external model call goes through the provider port, which writes the cost row with an effect key. No direct provider clients outside it.
5. **Transcript:**
   - identity is (session_id, seq);
   - every failed write is logged and counted — no silent `except`.
6. **Pipeline retries:** the attempt limit applies on every re-entry path (redelivery, stale sweep, manual).
7. **Account deletion:**
   - one registry covers every table, every object-storage prefix and every external grant (Nango);
   - the deletion event carries only ids.
8. **Object storage:**
   - explicit connect/read timeouts and a bounded retry policy;
   - no DB session held across storage calls.
9. **Task compatibility:**
   - new task arguments are optional;
   - consumers are deployed before producers;
   - an unknown task is an alert, not a silent drop.
10. **Configuration:**
    - Redis role addresses come from one config source;
    - scheduler loops run only in the scheduler process — the default is off;
    - all configuration comes from environment variables.
11. **Operations:**
    - every container has log rotation;
    - disk alert at 80%;
    - the release removes old images and keeps the previous one for rollback.
12. **Architecture tests:** import-linter contracts, the route and WS frame snapshots and the isolation test per read path are CI gates.
13. **Telemetry:**
    - trace context crosses every boundary: HTTP, WS, tasks, outbox events, egress;
    - telemetry never blocks a request;
    - no personal data or meeting text in logs, spans or metric labels.
14. **LLM-facing text:** prompts, tool descriptions and tool results are English only.

## 15. Security

- Access token: user id, home, company, `token_version`.
- Refresh sessions are revocable by version bump.
- Rights are not cached.
- RLS on company-scoped tables.
- The application role cannot modify the audit log.
- Secrets only from the environment. Tokens, passwords and keys are never logged.
- Recording and transcription are visible to all participants (indicator; consent at room entry).
- Signatures of acquirer webhooks are checked before parsing the body.
- Directory HMAC secret is stored outside the database.

## 16. Observability

Goal: for every user journey, answer "what is happening now and why" within minutes, and prove continuously that the invariants hold. Telemetry is kept short-term; it is not an archive.

### 16.1 Signals and stores

| Signal | Source | Transport | Store | Retention |
|---|---|---|---|---|
| Metrics | prometheus-fastapi-instrumentator; application metrics (RED per route template, queues, pools, WS slots, provider sessions); node, nginx and blackbox exporters | scrape | Prometheus | 30 days, size cap |
| Logs | structlog JSON on stdout | OpenTelemetry Collector (filelog → OTLP/HTTP) | Loki, single binary, local filesystem | 14 days, size cap |
| Traces | OpenTelemetry SDK: FastAPI, SQLAlchemy/asyncpg, HTTPX, Redis, TaskIQ, WS sessions | OTLP → OpenTelemetry Collector (tail sampling) | Tempo, single binary, local storage | 7 days |
| Client telemetry | web and desktop errors, Web Vitals, WS reconnects | API endpoint → logs | Loki | 14 days |
| Product facts | analytics events | outbox → analytics | PostgreSQL | analytics policy |

- One pane: Grafana with Prometheus, Loki and Tempo data sources — one ecosystem, native links between signals:
  - metric panel → trace through exemplars;
  - trace → its logs in Loki by `trace_id`;
  - log line → its trace through a derived field on `trace_id`.
- Log-based alerts are Loki ruler rules sent to the same Alertmanager.
- The application never waits on telemetry. The collector buffers with a bound and drops on overflow; drops are counted.

### 16.2 Correlation

- Trace context is propagated through HTTP, WS sessions, TaskIQ task headers, outbox events (trace id stored with the event) and the LiveKit egress stream.
- Every log line carries `trace_id`, `span_id`, `request_id`, and where known `home`, `org_id`, `user_id`, `session_id`.
- Every error returned to a client carries `request_id`, shown in the UI for support.

### 16.3 SLOs per journey

Alerts page on error-budget burn (fast and slow windows), not on causes.

| Journey | SLI | Objective |
|---|---|---|
| Sign-in | successful sign-ins / attempts; latency | 99.9%; p95 ≤ 300 ms (EU), measured separately for RU |
| Live capture | end of phrase → line on screen; sessions refused with 1013 | p95 ≤ 2 s; refused < 1% |
| Post-meeting | meeting end → notes ready; runs FAILED | p95 ≤ 10 min; failed < 1% |
| Payment | webhooks answered 2xx after commit; checkout success | 100%; 99.9% |
| Cabinet API | read latency per home | p95 ≤ 300 ms (EU); RU tracked, not paged (§20) |
| Leo | platform overhead per turn | ≤ 500 ms (EU) |

### 16.4 Invariant monitors

Each of these counters must stay at zero; any non-zero value pages.

| Monitor | Invariant |
|---|---|
| Transcript lines shown but not stored, checked per meeting at close | inv-6 |
| Payment acknowledged without a committed row, found by reconciliation | inv-4 |
| Provider calls without a cost row (provider port counter vs `provider_costs`) | inv-9 |
| Unknown task names dropped by workers | §14 rule 9 |
| Outbox events older than 5 min | events delivered |
| Dead-letter entries | inv-8 |
| Leftovers found by the post-deletion check of an account or company | nfr-13 |
| Access-policy decisions that disagree with RLS in the isolation self-test | inv-14 |

### 16.5 Dashboards

- One per journey (§16.3).
- One per process role: rate, errors, duration; event-loop lag, pool occupancy, WS slots, queue depth and age.
- One per home: DB latency, link availability for the Russian home, pool occupancy.
- One per AI provider: latency, errors, session pool, cost per hour.
- Per company and per user: through logs and traces, never through metric labels.

### 16.6 Alerting

- Page (Telegram via Alertmanager): SLO burn and invariant monitors. Every page links to a Grafana panel and a runbook.
- Ticket, not page:

| Signal | Threshold |
|---|---|
| Disk | 80% |
| Pools | 70% occupancy in either home |
| Oldest pipeline run | 10 min |
| Transcript queue | depth and age |
| Provider session pool | occupancy |
| Link to the Russian DB | latency |
| Unmatched bank payments | 24 h |
| Telemetry drops | > 0 |
| Uptime | external probe |

### 16.7 Cardinality, sampling, volume

- Metric labels are bounded: role, route template, status class, home, queue, provider. User, company and session ids appear only in logs and traces.
- Loki labels are bounded too: `service`, `role`, `level`, `home`. `trace_id`, `request_id`, `user_id`, `org_id`, `session_id` go to structured metadata, never to labels. A search by one of them is bounded by a time range — usually the range of the trace it came from.
- Traces: keep 100% of errors and of requests slower than their SLO, 5% of the rest (tail sampling in the collector).
- Logs: INFO by default; DEBUG only through a time-limited switch for one company or user.
- Volume at the design point (estimate): logs ≈ 20 M lines and ≈ 8 GB raw per day, ≈ 1–1.5 GB/day stored in Loki, cap 30 GB. Traces ≈ 140 000 per day, ≈ 10 GB for 7 days in Tempo. Prometheus cap 20 GB.

### 16.8 Privacy

- Telemetry lives in the EU plane. For Russian users it is a derived copy with short retention.
- No personal data, meeting text, transcript lines, prompts or tokens in logs, span attributes or metric labels — only ids.

## 17. Delivery and operations

- **Release:**
  - GitHub Actions builds the image from a green commit and pushes it to the registry;
  - `release.sh` deploys the registry image to staging, then to the plane;
  - no build on production hosts;
  - production secrets are not available to development sessions.
- **Order:** expand-only migrations applied to both homes by one release → task consumers → API → WS (drain with `server.shutdown`, up to 600 s).
- **Restore:** quarterly drill per home; runbooks written.
- **Pinned versions** for LiveKit, egress, coturn and Nango; they are updated by the common release.
- **Companies:**
  - bank statement reconciliation hourly;
  - unmatched payments → operator queue;
  - audit export on request by a company admin.

## 18. Technology stack

### 18.1 Base

| Area | Technology | Version | Purpose |
|---|---|---|---|
| Backend | Python | 3.14 | Backend language |
| Backend | FastAPI | latest stable | Async API |
| Backend | Pydantic | v2 | Schemas, validation, DTOs |
| Backend | pydantic-settings | latest stable | Configuration |
| Backend | SQLAlchemy (async) | 2.x | ORM and database access |
| Backend | Alembic | latest stable | Migrations |
| Backend | uv | latest stable | Package and project management |
| Backend | HTTPX | latest stable | Outbound HTTP calls |
| Backend | import-linter | latest stable | Architecture boundary checks |
| Frontend | React | 19.3 | UI |
| Frontend | TypeScript | latest stable | Typing |
| Frontend | Vite | latest stable | Build and dev tooling |
| Frontend | npm | — | Package management and scripts |
| Data | PostgreSQL | latest supported | Source of truth |
| Data | Qdrant | latest stable | Vector database, RAG |
| Data | Redis | latest stable | Cache, locks, rate limits, ephemeral state |
| Data | S3-compatible storage | — | Files, recordings, documents |
| Async work | TaskIQ | latest stable | Background jobs and workers |
| AI | Leo | — | Whisperer's AI agent |
| AI | LangGraph | latest stable | Agent orchestration, stateful workflows |
| AI | MCP | latest spec | Tool and external-agent integration |
| Observability | structlog | latest stable | Structured logging |
| Observability | OpenTelemetry | latest stable | Tracing and metrics |
| Testing | pytest, pytest-cov | latest stable | Tests and coverage |
| Testing | Hypothesis | latest stable | Property-based tests |
| Code quality | Ruff | latest stable | Lint and formatting |
| Code quality | mypy | latest stable | Static typing |
| Code quality | Radon, Vulture | latest stable | Complexity, dead code |
| Security | Bandit, Semgrep | latest stable | Security and code-pattern checks |
| Security | pip-audit | latest stable | Dependency vulnerabilities |
| Infrastructure | Docker, Docker Compose | latest stable | Containers; local and single-server orchestration |
| Infrastructure | NGINX | latest stable | Reverse proxy, TLS, static assets |
| Infrastructure | GitHub Actions | — | CI/CD |
| Contracts and docs | OpenAPI | 3.x | Contract between backend, frontend and clients |
| Contracts and docs | ADR | — | Record of architectural decisions |

### 18.2 Beyond the base

Versions are the latest stable releases as of 2026-09-30, the starting point for v2; the draft's versions are not carried over. Exact versions are pinned in the lock files and image tags and change only through a deliberate upgrade. Managed services run the provider's version; native clients are outside the rewrite.

| Area | Technology | Version | Purpose |
|---|---|---|---|
| Backend | Starlette | paired with FastAPI | ASGI toolkit under FastAPI |
| Backend | Uvicorn | 0.54.0 | ASGI server, one process per container |
| Backend | asyncpg | 0.31.0 | PostgreSQL driver |
| Backend | pgvector | 0.5.0 | Vectors in PostgreSQL |
| Backend | taskiq-redis | 1.2.4 | TaskIQ broker on Redis Streams |
| Backend | websockets | 17.1 | Streaming connections to AI providers |
| Backend | google-genai | 2.25.0 | Gemini Live client |
| Backend | aioboto3 | 15.5.0 | S3 client; one bucket per data home |
| Backend | livekit-api, livekit-protocol | 1.2.1, 1.1.27 | Video rooms and egress control |
| Backend | prometheus-fastapi-instrumentator | 8.1.0 | HTTP metrics |
| Backend | slowapi | 0.1.10 | Request rate limits |
| Backend | bcrypt, PyJWT, cryptography | 5.0.0, 2.15.1, 50.0.2 | Passwords and tokens; the token carries the data home |
| Backend | pypdf, python-docx, openpyxl, python-pptx, striprtf | — | Knowledge-base document parsing |
| Backend | tiktoken, rank-bm25, networkx | — | Token counting, keyword search, context graph |
| Testing | pytest-asyncio | 1.4.0 | Async tests |
| Code quality | python-doctor | — | Backend code-health gate |
| Data | PostgreSQL, managed (Timeweb, St Petersburg) | 18.4 | Russian data home |
| Data | PostgreSQL, managed (EU) | 18 | EU data home and the directory |
| Data | PgBouncer | transaction mode | Connection pooler in front of each database |
| Data | PostgreSQL row-level security | — | Second line of tenant isolation for companies |
| Data | Valkey, managed (Netherlands) | 9.1 | The managed Redis-compatible service: task queues, transcript queue, locks, meeting state, Leo checkpoints |
| Data | Redis, container | 8.10.2 | Local LRU cache |
| Data | S3 Timeweb ru-1 · S3 in the EU | — | Files of the Russian and EU data homes |
| Realtime and integrations | LiveKit server, egress, coturn | pinned | Video rooms, recording, per-participant tracks to the ws gateway, TURN |
| Realtime and integrations | Nango | pinned | OAuth proxy for connectors, one per data home |
| Realtime and integrations | Web Push (VAPID) | — | PWA notifications |
| Realtime and integrations | SMTP | — | Email |
| Realtime and integrations | Yandex SmartCaptcha | — | Form protection |
| AI providers | OpenRouter | — | Chat, vision, embeddings, rerank, web search |
| AI providers | OpenAI Realtime | — | Streaming speech recognition and translation |
| AI providers | Google Gemini Live | — | Voice assistant |
| AI providers | Deepgram, pyannote, Mistral OCR | — | Speech recognition, speaker diarization, document OCR |
| Payments | TBank, CloudPayments, lava.top | — | Card acquiring in RUB and foreign currency, incl. PayPal |
| Payments | Bank statement API | — | Reconciliation of company invoices; bank not chosen |
| Payments | Invoices, acts, UPD | — | Closing documents for Russian legal entities |
| Infrastructure | certbot, Let's Encrypt | 5.8.0 | TLS certificates; CA keys are pinned in shipped clients |
| Infrastructure | scripts/release.sh | — | Zero-downtime deploy of the CI-built image |
| Infrastructure | Container registry, staging | — | Built images; checks before production |
| Observability | Prometheus, Alertmanager, blackbox exporter, nginx exporter | 3.15.0, 0.34.1, 0.28.0, 1.5.3 | Metrics, Telegram alerts, external probes |
| Observability | node exporter | — | Host metrics and disk alert |
| Observability | OpenTelemetry Collector (contrib) | latest stable | One pipeline for logs and traces; tail sampling; bounded buffer |
| Observability | Loki | latest stable | Log store, 14 days on local filesystem with a size cap; alerts via ruler |
| Observability | Tempo | latest stable | Trace store, 7 days on local storage |
| Observability | Grafana | latest stable | One pane for metrics, logs and traces |
| Frontend | TanStack Query, React Router, Zustand | 5.104.0, 8.4.0, 5.0.15 | Data fetching, routing, state |
| Frontend | i18next, react-i18next | 26.4.2, 17.0.15 | 16 languages |
| Frontend | Tailwind CSS, Mermaid | 4.3.3, 12.0.0 | Styles; diagrams in answers |
| Frontend | Vitest, react-doctor | 5.0.3, 0.9.14 | Tests; React code-health gate |
| Clients | macOS, iOS: Swift, SwiftUI, WhispererKit | Swift 6 | Apple desktop and mobile clients |
| Clients | Linux: Swift, WhispererKit, GTK 4, PipeWire | Swift 6 | Linux desktop client |
| Clients | Windows: C#, .NET, WPF, WebView2, CommunityToolkit.Mvvm, NAudio | .NET 10 | Windows desktop client |

## 19. Decisions

| Decision | Why | Cost | Revisit when |
|---|---|---|---|
| One compute plane in the EU, two data homes | AI reachable directly; one deployment and one release; audio does not cross the border; clients keep one base URL | Russian requests spend 180 ms in the DB; derived data of Russian users in the EU; the RU link stops Russian users | a lawyer rules derived copies abroad inadmissible; p95 cabinet reads from Russia > 300 ms; link availability < 99.9%/month → move compute for Russian users next to their DB |
| Directory with the home in the token | one login without shared primary data; directory off the request path | registration and transfer depend on the EU DB; 60-s cache → transfer bumps token version | email HMAC ruled personal data that cannot leave Russia → separate logins per home |
| Transcript line: seq, durable Redis queue before display, 500-ms batches | inv-6 and nfr-9 without a DB next to the plane; ≈ 4 held connections instead of 62 | ≈ 2 ms to display; up to 1 s to the DB; Redis becomes part of capture durability | compute moves next to the Russian DB → insert before display; Redis loses data on failover more than once a quarter |
| PgBouncer and one pool per database per process | pool sum under the server limit | transaction mode forbids session-bound features (prepared statements, session locks, LISTEN) — each use must be checked | the managed database provides a built-in pooler |
| Provider port writes every cost row | inv-9; spend guards see every call | all provider clients created in one place | never |
| Shared Redis and Qdrant in the EU | one set of services for one operator | derived data of Russian users outside Russia | a regulator or contract requires derived data in Russia |
| WS process pool sized by configuration; 1013 when full | 2 600 concurrent meetings with Docker Compose | manual capacity; reserve idles | peak exceeds capacity more than monthly, or > 20 WS processes needed |
| Events through the outbox and TaskIQ | single-digit events per second need no extra stateful cluster | no attachment point for consumers outside the application; replay limited to 7 days | see §12 |
| Delayed actions as `errands` rows run by the scheduler | "wait, then act once" needs no extra cluster | multi-step waiting scenarios are hand-written | see §12 |
| Company = new ownership level (`org_id` + access level) | shared team space without copying data | every read path of shared domains changes | < 5% of company resources shared after six months → freeze sharing, keep seats and billing |
| One access policy, no caching of rights, RLS as second line | nfr-15, inv-14 | `SET LOCAL` per transaction; separate role for migrations and sweeps | RLS overhead > 10% of query time and isolation tests cover every read path |
| Work account in the company home, personal account separate | all company data in one home | two accounts for one person | users widely demand one identity for both spaces |
| Search and Leo re-check hits in the DB | index payload lags access changes | one extra DB query per search | never |
| Room transcription via LiveKit track egress | exact speaker, live transcript; a component already in the stack | egress joins the live path; one provider stream per track | egress cannot hold the needed tracks per process → revisit the track ingest path |
| Invoices matched by bank statement | legal entities pay without an acquirer | closing documents, tax, manual queue for unmatched | < 20 invoices a month → manual reconciliation |
| Audit row in the action's transaction | nfr-17, inv-17 without a separate store | one insert per admin action | never |
| Domain join + invitations; SSO and SCIM later | self-service onboarding for 5–200 seats | large customers need more | first customer with 200+ seats requires enterprise sign-in |
| Commit before response; acquirer call outside the transaction; subscription row lock | inv-3, inv-4, nfr-10 | checkout becomes two transactions with an "invoice requested" state to reconcile | never |
| CI-built images, registry, staging; production secrets closed to development | red code cannot reach production; development cannot break production | slower release; staging cost | never; staging may be stopped between releases |
| Grafana stack for observability: Prometheus, Loki, Tempo, Grafana | one ecosystem: native links metric → trace → logs; log alerts through the Loki ruler into the same Alertmanager; S3 storage available for Loki and Tempo when needed | label discipline in Loki; ad-hoc search by a high-cardinality field scans lines within the time range | ad-hoc searches by user or company over long periods become routine, or logs grow far beyond ≈ 1.5 GB/day stored → revisit the log store |
| Tempo for traces, 7 days on local storage | native Grafana integration: TraceQL, trace → logs in Loki, exemplars from Prometheus | one more store; tail sampling needed | trace volume outgrows the local disk → Tempo on S3 |
| One OpenTelemetry Collector for logs and traces | the application is independent of the stores; tail sampling in one place | one more process to run | never |
| Presigned uploads directly to the home bucket; lifecycle rules | no DB session or API process held by file transfer | two-step upload; abandoned uploads removed by bucket rules | the storage provider lacks presigned multipart or lifecycle rules |

## 20. Accepted trade-offs

- Russian users: cabinet and Leo latency bound by 45 ms per DB round trip. nfr-7 is not met for them.
- Derived copies of Russian users' and companies' data live in the EU (§6).
- Availability for Russian users = plane × link to the Russian DB.
- A Redis failover can lose up to 1 s of transcript lines.
- 99.9% of meeting capture excludes the AI provider; its outage degrades capture.
- Double loss of a DB cluster restores in up to 4 h (beyond nfr-3).

## 21. Out of scope

- Own speech or language models in Russia.
- A third jurisdiction (US, Asia): a home is added the same way when needed.
- Collaboration between companies and one company across two homes; outside a company only public links.
- Dedicated installations for companies (their cloud or servers).
- Bots that join third-party video meetings.
- Enterprise sign-in and SCIM (fr-17) — next step.
- Electronic document exchange with counterparties.
- Sharding a home DB before 100 000 DAU.

## 22. Open items

| Item | Owner | Needed before |
|---|---|---|
| Legal review: email HMAC outside Russia; derived copies in the EU; telemetry without an account in the EU home (ADR 0005); data of people outside Russia kept in the Russian home until their transfer (ADR 0004); cross-border transfer to AI providers; processor agreement (152-FZ) and DPA (GDPR) with the list of subprocessors | owner, lawyer | first transfer of accounts; first company contract |
| Tax, closing documents, document exchange for Russian legal entities | owner, accountant | first invoice |
| Provider of the EU PostgreSQL and EU S3; bank for statement API | owner | building the EU home; first invoice |
| Provider quotas for 2 600 concurrent recognition and voice sessions | owner | 1 000 concurrent meetings |
| Seat price ≥ recognition cost ($7.92–15.84 per seat per month) plus models | owner | announcing prices |
| Measurement gates: link plane → Russian DB (latency, availability, one month); Redis latency from WS processes (< 5 ms); meetings per WS process under a real provider; tracks per egress and per WS process; RLS overhead on meeting read and search | engineering | the corresponding step |
