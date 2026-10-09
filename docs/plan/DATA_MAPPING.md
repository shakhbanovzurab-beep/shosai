# Data inventory and mapping: draft → v2

- **Package:** D3 of [the rewrite plan](REWRITE_PLAN.md). Prompt: [prompts/D3-data-mapping.md](prompts/D3-data-mapping.md).
- **Readers:** every slice that designs tables (S01–S17) and M1, which moves production data.
- **State of the draft:** `/root/whisperer` at Alembic head `167` (166 migrations), read on 2026-10-01.
- **Status:** complete. The owner took the decisions of [section 10](#10-decisions-for-the-user) on 2026-10-01; those that change the architecture are recorded in [ADR 0004](../adr/0004-migrated-accounts-start-in-russian-home.md), [ADR 0005](../adr/0005-data-without-owner-in-eu-home.md), [ADR 0006](../adr/0006-draft-bucket-becomes-russian-home-bucket.md) and [ADR 0007](../adr/0007-usage-tombstones-kept-for-lifetime-quota.md), and the target architecture is updated accordingly.
- `§` numbers refer to the [target architecture](../design/ARCHITECTURE.md). "Section N" refers to this document.

**How this was built.** No production system was touched.

1. The draft schema was built by running all draft migrations on a throwaway local PostgreSQL 16 with pgvector, then read from the catalogue. The ORM metadata was compared with it.
2. Every table, S3 prefix, local-disk location and Redis key family was traced in the draft code: writers, readers, owner, secrets, lifecycle, deletion.
3. Each item was mapped to v2 under §4–§9 and §12–§14, and to the owning slices and decisions of the [feature map](FEATURE_MAP.md) (D4, FM-1…FM-5).

To reproduce step 1, run `alembic upgrade head` from a copy of the draft's `backend/` against an empty pgvector database, with only `DATABASE_URL` set. No `.env` is involved.

---

## 1. Summary

**Inventory.**

| Store | Size of the inventory |
|---|---|
| PostgreSQL | 131 application tables plus `alembic_version`; 1 458 columns; 359 constraints; 249 secondary indexes; extensions `vector`, `pg_trgm`; one range-partitioned table; one trigger; two sequences |
| Object storage | One bucket, 9 key prefixes (O1–O9) |
| Local disk | 3 locations on the API host (L1–L3) |
| Redis / Valkey | 13 key families with durable or in-flight state; the rest are locks, limits and caches |
| Other stateful services | Nango schema, Temporal, NATS JetStream, Qdrant |

**Mapping.** Of 131 tables, 86 move unchanged, 30 are transformed, 5 are derived (rebuilt by v2) and 10 are dropped. Of the 1 458 columns, 1 317 move unchanged, 14 are transformed, and 89 belong to dropped tables or are dropped individually. The other 38 belong to derived tables or are derived individually. Section 5 has every table; Appendix A has every column with its type.

**Facts that shape the migration.**

1. **All production data lives in Russia today.** The draft runs on managed PostgreSQL 18.4 in St Petersburg and one Timeweb S3 bucket (default region `ru-1`). This holds for EU users too. Production was restarted empty on 2026-07-31, so the data set is two months old.
2. **The draft has no companies.** Every row is personal. The v2 company tables (§7) start empty.
3. **Identifiers are load-bearing.** Acquirer order ids are built from `transactions.id`, and the renewal key from `subscriptions.id`. Share links, invitation links, calendar URLs and webhooks embed ids and tokens. Every id and token is copied verbatim (R1).
4. **Transcript lines have no `seq`.** v2 identity is `(session_id, seq)`. M1 derives `seq` from the draft order (T-1).
5. **Secrets must travel with the data.** The JWT secret, the Fernet key ring, the Nango encryption key and the VAPID key pair are needed. Without them users are signed out, or every integration needs re-consent (R6, S-1, S-3).
6. **The draft leaves data behind on deletion.** Meeting audio, raw recognition output, knowledge-engine originals, exports, context files and external grants survive account deletion. v2's deletion registry covers them. What the draft left behind is not carried over (D-2).
7. **The owner took ten decisions on 2026-10-01** (section 10). The main ones: existing accounts start in the RU home (U-1), and data without an owning account lives in the EU home (U-2, U-8).
8. **Some knowledge documents may have no content anywhere.** Onyx-era uploads and vault notes kept only as a fingerprint have no bytes in our storage. M1 recovers what it can and lists the rest (T-4, U-11).

---

## 2. How to read this document

**Actions.**

| Action | Meaning |
|---|---|
| moved | Copied as is: same values, same column names |
| transformed | Copied with a stated change: row filter, new column, renamed table, new partitioning, re-pointed object |
| derived | Not copied; v2 rebuilds it from a named source |
| dropped | Not copied; the reason is stated. A drop of user data is listed in section 10 for the owner's decision |

**Columns.** A column not named under its table moves unchanged, with the same name and type (Appendix A). The table names are proposals. The slice that owns a table may rename it or its columns; it updates this document in the same commit, so M1 always reads one mapping.

**Owner → home.** Each table says how a row finds its owning account. The owner's home is the row's home (R2). "Platform" rows have no owner and follow R12.

**IDs used below.**

| Prefix | What it names | Where |
|---|---|---|
| R | Global rules | Section 4 |
| O, L | Object prefixes and local-disk locations | Section 6 |
| M, E, T, A, D, S, F | Risks with their verification | Section 8 |
| U | Decisions of the owner | Section 10 |

---

## 3. The draft data estate

### 3.1 PostgreSQL

| Item | Draft at head 167 |
|---|---|
| Server | Managed PostgreSQL 18.4, St Petersburg (production). Local reproduction used 16 + pgvector |
| Schemas | `public` (application); `nango` (Nango's own tables, section 7.4) |
| Extensions | `vector`, `pg_trgm`, `plpgsql` |
| Tables | 131 + `alembic_version` (dropped: v2 has its own migration history) |
| Keys | UUID primary keys everywhere except `calendar_sync_notifications` (bigint sequence) and composite keys of link tables |
| Partitioned | `analytics_events`: RANGE on `ts`, monthly partitions `analytics_events_YYYY_MM`; created and dropped by the task `analytics.maintain_partitions` (24-month retention) |
| Trigger | `knowledge_document_release_usage` (AFTER DELETE, statement level) calls `knowledge_release_usage()`, which decrements `knowledge_space.used_bytes` |
| Sequences | `ticket_number_seq` (ticket numbers, start 100000); `calendar_sync_notifications_id_seq` |
| Foreign keys | 150: 115 `CASCADE`, 27 `SET NULL`, 8 that block deleting the parent (no action: `transcript_segments`, `meeting_map_nodes` and `prompt_executions` → `sessions`; `prompt_executions` → `prompt_templates`; `RESTRICT`: `tracker_tasks` → `tracker_statuses` and three keys to `tariffs`) |
| Checks | 5 (`pcg_facts` refutation pair, `promo_codes.used_count ≤ max_uses`, satisfaction score 1–5, tracker status category, tracker priority) |
| Functional and partial unique indexes | Case-insensitive names: `meeting_tags`, `tracker_projects`, `tracker_statuses`, `tracker_labels`. Partial: `uq_transactions_external_id`, `uq_recurring_active_per_user`, `uq_usage_events_session`, two on `knowledge_document`, two on `meeting_workspace_impacts`, `ux_prompt_role_default_per_role` |
| Search indexes | HNSW on `embeddings`, `memory_items`, `meeting_segment_embeddings`; trigram GIN on transcript text, meeting notes, session titles and calendar events |

**Owner columns without a foreign key.** Cleanup of these relies on the deletion registry alone:

- `connector_connections`, `leo_personalization`, `satisfaction_surveys`, `analytics_events`, `analytics_identity`, `memory_items`;
- `pcg_entities`, `pcg_edges`, `pcg_facts`;
- `hubs`, `hub_meetings`, `hub_rules`, `hub_materials`;
- the six `proactive_*` tables and `errands`;
- the denormalised `user_id` of `meeting_speakers`, `meeting_processing_runs`, `meeting_workspace_impacts`, `meeting_segment_embeddings`.

**Models versus migrations.** Tables, columns and types agree exactly. They differ in two ways:

- **Index and constraint names**, which do not matter for data.
- **Nullability of 46 columns.** For 45 the database allows NULL where the model says NOT NULL: `created_at` in 43 tables, `notes.modified_at`, `prompt_templates.is_active`. The reverse holds for `usage_events.updated_at`. R10 covers these columns.

**Deletion in the draft.** `services/account_data.py` keeps a registry of user tables in three classes:

- CONTENT, erased by "delete all";
- ACCOUNT, erased with the account;
- FINANCIAL (`transactions`, `provider_costs`, `premium_credit_ledger`, `affiliate_commissions`), kept forever.

Because the money tables reference `users` with ON DELETE CASCADE, a deleted account's `users` row is anonymised rather than deleted. `analytics_events` and `analytics_identity` are exempt by design and keep the `user_id` of deleted accounts.

### 3.2 Other stores

| Store | Draft use | Section |
|---|---|---|
| S3 (Timeweb) | One bucket `s3_bucket`, 9 prefixes; server-proxied uploads, presigned GET only; no lifecycle rules in the repository | 6 |
| Local disk | Volume `app_data`: desktop builds and personal context files; volume `app_kb`: watched, never written by code | 6 |
| Redis / Valkey | Managed Valkey 9.1. Holds TaskIQ streams, Leo checkpoints, pending registrations, spend counters, dedup markers, locks, limits, caches; plus an optional local LRU cache | 7.1 |
| NATS JetStream | Domain events relayed from the outbox (`WHISPERER_EVENTS`, 7 days) and a DLQ (30 days) | 7.2 |
| Temporal | Execution of errands, in its own PostgreSQL | 7.3 |
| Nango | OAuth tokens of connectors, schema `nango` in the production database | 7.4 |
| Qdrant | Index of the new knowledge engine; dormant unless `QDRANT_URL` is set | 7.5 |

---

## 4. Global rules

These rules apply to every table unless its entry in section 5 says otherwise.

**R1. Identifiers are preserved.** Every primary key and every external or secret identifier is copied verbatim. This includes order ids, tokens, hashes, ciphertexts, LiveKit names and calendar channel ids. New v2 rows get UUIDv7 where §8.2 asks; migrated UUIDv4 values coexist, because partitions are keyed by time, not by id. Content-derived ids (UUIDv5 of knowledge versions and chunks) are preserved as well.

**R2. Every row lives in its owner's home** (§4.1, §6). The draft stores no country of residence. Available signals are weak and partly missing:

- request geo snapshots in `analytics_events.country` and `satisfaction_surveys.country`;
- `users.language`, `users.timezone` and the optional `users.phone`;
- quick sign-in with Yandex ID or VK ID, which exist only for Russia;
- transaction currency and acquirer: TBank for RUB, lava for foreign currency.

*Decided (U-1, [ADR 0004](../adr/0004-migrated-accounts-start-in-russian-home.md)):*

1. M1 places every existing account in the **RU home**, where its data already is, so nothing crosses a border at cutover.
2. Users outside Russia are then moved to the EU home by the account-transfer saga (fr-7) once the EU home exists. They are selected by a country they confirm in the product; the signals above only choose whom to ask.

**R3. Every migrated row is personal.** The draft has no companies. Company-scoped columns are filled as follows:

| Column | Value |
|---|---|
| `org_id` | NULL |
| `access` | The personal default that S02 defines, on resources with company access (§7: meetings, notes, folders, knowledge collections) |
| `resource_grants`, `organizations`, `memberships`, `directory_domains`, `org_invoices`, `org_audit_events` | No rows |

`users.org_id` is NULL, because no work accounts exist.

**R4. Directory.** M1 writes one `directory_entries` row (§6, §8.1) per account that is not anonymised:

| Field | Value |
|---|---|
| `email_hmac` | HMAC of the normalised email under the v2 directory secret. The draft stores emails lowercased; the v2 normalisation (S01) is applied to them |
| `user_id` | `users.id` |
| `home` | From R2 |
| `state` | From `users.status` (`active`, `frozen`, `banned`) |
| `version` | Initial |

Two accounts whose emails normalise to the same value block the run (S-2).

**R5. Anonymised accounts.** These are rows with `email = 'deleted-<id>@deleted.invalid'`, `status = 'banned'` and a random password hash.

- **Moved:** the account row, because `transactions`, `provider_costs`, `premium_credit_ledger` and `affiliate_commissions` keep referencing it for five years (402-FZ).
- **No directory entry:** their address is gone, so no HMAC can be computed.
- **Home:** the home of their financial rows, which is RU under R2.

**R6. Secrets travel with the data; M1 never decrypts.** Ciphertexts, hashes and plaintext link secrets are copied byte for byte. v2 must be configured with the draft's keys, under the same production-secret handling as its own:

| Secret (setting) | Protects | Without it |
|---|---|---|
| `jwt_secret` (HS256) | Access and refresh tokens (`sub`, `typ`, `tv`, `fid`, `jti`); also social-login state, unsubscribe links, share tickets | Every user and every desktop client is signed out; unsubscribe and share-ticket links break |
| `fernet_key`, `fernet_keys_previous` | `oauth_accounts.*_enc` (active key only, no ring); `recurring_payment_methods.rebill_id_ciphertext` (active key only); MCP, CalDAV, meeting-integration and knowledge-source ciphertexts (ring) | Saved cards cannot be charged; every OAuth, CalDAV, MCP and push integration needs re-consent |
| `NANGO_ENCRYPTION_KEY` | All tokens in the `nango` schema; cannot be rotated | Every connector needs re-consent |
| VAPID key pair | `proactive_push_subscriptions` | Every browser push subscription dies |
| OAuth app credentials and redirect URIs (Google, Microsoft, Jira, Yandex, VK, Nango callback) | Refresh of existing grants | Re-consent |

Draft access tokens carry no home claim. For their remaining life (≤ 30 minutes), S01 resolves the home of such a token through the directory, and the next refresh issues a v2 token.

**R7. Derived stores are rebuilt, not copied** (§8.2, inv-10):

| Draft store | Source v2 rebuilds it from |
|---|---|
| Vectors of `meeting_segment_embeddings` (1536-dim, per segment) | `transcript_segments`, as per-minute windows by cursor: `sessions.indexed_upto_seq = 0` at migration |
| Vectors of `embeddings` (384-dim, legacy notes) | `notes` |
| `memory_items.embedding` (384-dim) | `memory_items.text` |
| Qdrant collection `knowledge` | `knowledge_node` and the originals |
| `knowledge_chunk`, `knowledge_job` | `knowledge_node` and the originals |
| `chunks` | `notes`, as knowledge-base items (FM-2) |
| Redis caches, including `memory:summary:*` | Their own jobs |

The model and dimension change in v2 (§3: 512-dim windows), so copied vectors would be useless. Whether vectors live in Qdrant or pgvector is undecided (CLAUDE.md); this rule holds either way. The rebuild costs embedding calls, estimated in section 9.

**R8. Partitioned tables** (§8.2). These tables get monthly partitions:

| v2 table | Draft table | Partition key |
|---|---|---|
| `transcript_segments` | `transcript_segments` | `started_at` |
| `provider_costs` | `provider_costs` | `created_at` |
| `prompt_executions` | `prompt_executions` | `created_at` |
| `usage_events` | `usage_events` | `created_at` |
| `login_events` | `login_events` | `created_at` |
| `error_logs` | `error_logs` | `created_at` |
| `client_errors` | `client_error_logs` | `created_at` |
| `agent_audit` | `agent_audit_log` | `created_at` |
| `analytics_events` | `analytics_events` | `ts` (as in the draft) |

- **Before loading:** M1 creates every partition between the oldest and the newest row.
- **Primary keys:** a partitioned table's primary key includes the partition key. The draft `id` stays unique and is verified as such (A-1).
- **Retention:** applied by the slice after cutover, never by M1.

**R9. Transient rows are filtered at the freeze instant `T0`.** One-time codes, dead sessions, expired links and short-lived queues do not move. Each table states its filter in section 5.

**R10. NULLs in columns that v2 declares NOT NULL.** These are the 45 columns of section 3.1.

- M1 counts NULLs per column before loading. Zero is expected, because every draft insert passes through the ORM.
- A NULL `created_at` gets the row's best other timestamp (`updated_at`, `started_at`), else `T0`. A NULL `prompt_templates.is_active` gets `false`, the model default.
- Every filled value is counted in the run report.

**R11. Soft references and orphans.**

- **Orphans.** A row whose owner cannot be resolved does not move. The owner may be a missing user, or a NULL `sessions.user_id` on a legacy row. M1 reports such rows per table with counts, for the owner's decision (U-4).
- **Other soft references** are copied even when they dangle, and their dangling count is reported:
  - kind/id pairs in `pcg_edges`, `hub_materials`, `proactive_nudges.evidence`;
  - `meeting_speakers.person_entity_id`;
  - `hub_meetings.session_id`;
  - the `document_id` of `knowledge_document_version`, which points to `knowledge_document` or to `sessions`.

**R12. Platform rows.** Some tables have no owning account:

- `tariffs`, `promo_codes`, `payment_routes`, `exchange_rates`;
- `models_registry`, `model_defaults`;
- `mcp_registered_clients`, `broadcasts`, `error_logs`, `app_builds`;
- the `user_id IS NULL` rows of `prompt_templates` and `notes` (S07 decides the fate of the notes ones, FM-2).

*Decided (U-2, [ADR 0005](../adr/0005-data-without-owner-in-eu-home.md)):* they live in the **EU home**, next to the directory, with one writer. Home tables reference them by id without a foreign key, and platform ids are never deleted, only retired.

Anonymous telemetry has no owner either: `analytics_events` and `client_error_logs` rows without a user. *Decided (U-8, [ADR 0005](../adr/0005-data-without-owner-in-eu-home.md)):* it goes to the EU home too.

**R13. Load order and constraints.**

1. Parents load before children. The FKs without a delete action fix part of the order: `tariffs` before subscriptions and consents; `tracker_statuses` before `tracker_tasks`; `sessions` and `prompt_templates` before their children.
2. Self-references load parent first, or with deferred constraints: `storage_files.parent_id`, `meeting_folders.parent_id`, `knowledge_node.parent_id`, `calendar_events.parent_event_id`, `users.referred_by_user_id`.
3. Secondary indexes are built after the bulk load.
4. The knowledge release-usage trigger is created after `knowledge_document` is loaded (E-6).
5. `ticket_number_seq` is set past the highest migrated number in its home.

**R14. Freeze preconditions.** M2 owns the cutover runbook. M1 refuses to start unless all of these hold at `T0`:

- the draft is in maintenance mode, its scheduler and workers are stopped, and no meeting, room or stream is live;
- `auto_charge_attempts` has no row in `charging`, and payment reconciliation has run after the last webhook (M-2);
- `outbox_messages` has no unpublished row, and the NATS consumers have no lag;
- the TaskIQ streams and the legacy TaskIQ lists are empty;
- errands are copied before the Temporal workflows are cancelled (section 7.3).

---

## 5. Table mapping by v2 slice

**Tables that exist only in v2.** M1 fills these:

| Table | Content |
|---|---|
| `directory_entries` | R4 |
| `nango` schema of the RU home | Copied whole, section 7.4 |

These start empty: `directory_domains`, `organizations`, `memberships`, `resource_grants`, `org_invoices`, `org_audit_events`, `home_transfers`, `processed_events`, `schedule_runs`. A missed periodic interval runs once on start (§12).

**Per slice.** S02 (organizations), S05 (realtime) and S17 (public site) receive no draft tables. Following D4, the broadcast and whiteboard tables belong to S06, and the provider cost, metering and abuse tables to F6 (FM-4); `exchange_rates`, mapped in 5.2, belongs to F6 since [ADR 0036](../adr/0036-exchange-rate-owned-by-platform-services.md).

| Slice | Tables | moved | transformed | derived | dropped |
|---|---|---|---|---|---|
| S01 Identity | 9 | 2 | 5 | 0 | 2 |
| S03 Billing | 16 | 15 | 1 | 0 | 0 |
| S04 Meetings | 17 | 12 | 4 | 1 | 0 |
| S06 Rooms | 10 | 8 | 0 | 0 | 2 |
| S07 Knowledge and search | 15 | 5 | 4 | 4 | 2 |
| S08 Storage | 1 | 1 | 0 | 0 | 0 |
| S09 Agent (Leo) | 18 | 12 | 4 | 0 | 2 |
| S10 MCP | 5 | 4 | 1 | 0 | 0 |
| S11 Errands | 1 | 0 | 1 | 0 | 0 |
| S12 Connectors and calendar | 13 | 11 | 1 | 0 | 1 |
| S13 Tracker | 5 | 5 | 0 | 0 | 0 |
| S14 Analytics | 4 | 1 | 3 | 0 | 0 |
| S15 Administration and support | 5 | 3 | 2 | 0 | 0 |
| S16 Hub, downloads and remaining modules | 5 | 4 | 1 | 0 | 0 |
| F1 Backend foundation (platform tables) | 1 | 0 | 0 | 0 | 1 |
| F6 Platform services (FM-4) | 6 | 3 | 3 | 0 | 0 |
| **Total** | **131** | **86** | **30** | **5** | **10** |

Columns: 1458 in mapped tables — 1317 moved, 14 transformed, 38 derived, 89 dropped (columns of derived and dropped tables are counted with their table).

### 5.1 S01 — Identity

#### `users` → `users` · **transformed**

- **Owner → home:** the row itself (the account).
- **Columns:** 30 of 39 move unchanged; exceptions:
  - `email` — *moved*. Stored lowercased; its normalised form is the input of `directory_entries.email_hmac` (rule R4). Anonymised placeholders `deleted-<id>@deleted.invalid` get no directory entry (R5).
  - `password_hash` — *moved*. Bcrypt, verbatim; `deleted-<hex>` values of anonymised accounts stay.
  - `token_version` — *moved*. Verbatim: it is the `tv` claim of every live access and refresh token (R6).
  - `ical_token` — *moved*. Verbatim: it is the secret in published calendar-subscription URLs.
  - `storage_used_bytes` — *moved*. Verbatim, then checked against `SUM(storage_files.size)` (F-1).
  - `no_logs_minutes_used` — *moved*. Verbatim: lifetime quota input (E-2).
  - `ai_minutes_used` — *moved*. Verbatim: lifetime quota input (E-2).
  - `referred_by_user_id` — *moved*. Becomes a soft reference when referrer and referred end up in different homes.
  - `avatar_url` — *moved*. Inline base64 data URL, kept in the row.
- **New in v2:** `home` — `ru` or `eu` by rule R2.
- **New in v2:** `org_id` — NULL: the draft has no work accounts (R3).
- `email_verified` is always true in the draft; moved as is.
- Anonymised accounts (R5) are moved because the money tables reference them.

#### `refresh_sessions` → `refresh_sessions` · **transformed**

- **Owner → home:** own `user_id`.
- **Rows:** only live families: `revoked_at IS NULL AND expires_at > cutover`; the rest are dropped (dead sessions, no use).
- **Columns:** 9 of 13 move unchanged; exceptions:
  - `current_jti` — *moved*. Verbatim; `id` is the `fid` claim, so live refresh tokens keep rotating (R6).
  - `prev_jti` — *moved*. Verbatim (10-second double-refresh grace).
  - `ip` — *moved*. Personal data, lives in the owner's home.
  - `user_agent` — *moved*. Personal data.
- No sweep exists in the draft; expired rows are the bulk of the table.

#### `user_identities` → `user_identities` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 8 move unchanged.
- Yandex ID and VK ID links; no provider tokens are stored.

#### `desktop_auth_codes` → `desktop_auth_codes` · **dropped**

- **Owner → home:** own `user_id`.
- **Columns:** 7, none copied.
- One-time browser→desktop codes with a 120-second life; none survives a maintenance window and used ones have no further use. The v2 table starts empty.

#### `email_verification_codes` → no v2 table · **dropped**

- **Owner → home:** own `user_id`.
- **Columns:** 8, none copied.
- Dead table: pending registrations live in Redis (`pending_reg:*`), and no code reads or writes these rows. All rows are expired.

#### `password_reset_tokens` → `password_reset_tokens` · **transformed**

- **Owner → home:** own `user_id`.
- **Rows:** only `used_at IS NULL AND expires_at > cutover`, so reset links mailed shortly before the window still work; the rest are dropped.
- **Columns:** 6 of 7 move unchanged; exceptions:
  - `token_hash` — *moved*. Sha-256, verbatim.

#### `login_events` → `login_events` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** 3 of 6 move unchanged; exceptions:
  - `created_at` — *transformed*. Partition key: monthly partitions per §8.2; rows with NULL get `now()` at migration and are counted (R10).
  - `ip` — *moved*. Personal data.
  - `user_agent` — *moved*. Personal data.
- `outcome` is always `success` in practice (no writer of `failed`).

#### `user_onboarding` → `user_onboarding` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 13 move unchanged.

#### `data_export_jobs` → `data_export_jobs` · **transformed**

- **Owner → home:** own `user_id`.
- **Rows:** `status='ready' AND expires_at > cutover` move together with their archive; `pending`/`running` move as `pending` and are re-run by v2; the rest are dropped with their objects (D-4).
- **Columns:** 8 of 10 move unchanged; exceptions:
  - `s3_key` — *transformed*. Rewritten if the archive is copied to a new key (section 6).
  - `error` — *moved*. User-facing text.

### 5.2 S03 — Billing

#### `tariffs` → `tariffs` · **moved**

- **Owner → home:** platform catalog (R12).
- **Columns:** 16 of 17 move unchanged; exceptions:
  - `code` — *moved*. Verbatim: the tier is derived from the code prefix (`free`, `start`, `pro_*`, `max_*`).
- Copy production rows, not migration seeds: the admin UI edits prices and limits.

#### `subscriptions` → `subscriptions` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 6 of 13 move unchanged; exceptions:
  - `id` — *moved*. Verbatim: part of the renewal idempotency key `{subscription.id}:{date}`.
  - `expires_at` — *moved*. Absolute timestamp verbatim; never recomputed from transactions (E-1).
  - `status` — *moved*. Only `active` is ever written; expiry is judged by `expires_at`.
  - `premium_credit_usd` — *moved*. Authoritative credit balance (M-3).
  - `credits` — *moved*. Admin ruble bonus; shown, never spent.
  - `renewal_provider` — *moved*. NULL = we renew by saved card; `lava` = the acquirer renews.
  - `tariff_id` — *moved*. Soft reference to the catalog in the EU home (U-2).

#### `subscription_segments` → `subscription_segments` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 7 of 8 move unchanged; exceptions:
  - `remaining_days` — *moved*. Verbatim: a bank of paid days that does not tick while frozen.
- Moved together with the owner's subscription; the paid time of a user is the active window plus these days.

#### `transactions` → `transactions` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 14 of 21 move unchanged; exceptions:
  - `id` — *moved*. Verbatim: acquirer order ids are `tb_<id.hex>` and `cp_<id.hex>`.
  - `external_id` — *moved*. Verbatim; the partial unique index on it is the webhook idempotency key.
  - `method` — *moved*. `tbank`, `lava`, `lava_paypal`, `cloudpayments`, and legacy `moneta`; history stays readable.
  - `amount` — *moved*. Numeric(12,2) in `currency`.
  - `amount_rub` — *moved*. Whole rubles, not kopecks.
  - `referral_applied_rub` — *moved*. Pending and successful rows both count as spent referral balance (M-4).
  - `tariff_id` — *moved*. Soft reference to the catalog in the EU home (U-2).
- Never deleted (402-FZ). The first transaction of a lava subscription is its parent contract; dropping it orphans acquirer renewals.

#### `auto_charge_attempts` → `auto_charge_attempts` · **moved**

- **Owner → home:** via `subscription_id` → `subscriptions.user_id`.
- **Columns:** 9 of 10 move unchanged; exceptions:
  - `renewal_period_key` — *moved*. Verbatim: unique per subscription, prevents a second charge for the period.
- Precondition: no row in `charging` at freeze (M-2).

#### `auto_renew_consents` → `auto_renew_consents` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 12 move unchanged.
- Legal evidence of consent (376-FZ); without an active consent nothing is charged.

#### `card_bindings` → `card_bindings` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 9 of 10 move unchanged; exceptions:
  - `hold_ref` — *moved*. Verbatim: an unreleased hold is the user's money held at the acquirer (M-5).

#### `recurring_payment_methods` → `recurring_payment_methods` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 9 of 11 move unchanged; exceptions:
  - `rebill_id_ciphertext` — *moved*. Byte-for-byte; Fernet, key `fernet_key` (R6).
  - `customer_key` — *moved*. Verbatim: `user_id.hex`, sent to the acquirer on every charge.
- Partial unique index: one `active` row per user.

#### `premium_credit_ledger` → `premium_credit_ledger` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 10 move unchanged.
- Audit of credit grants and debits; never deleted. The balance in `subscriptions.premium_credit_usd` is authoritative and may differ from `SUM(delta_usd)` because of clamping (M-3).

#### `promo_codes` → `promo_codes` · **moved**

- **Owner → home:** platform catalog (R12).
- **Columns:** 8 of 9 move unchanged; exceptions:
  - `used_count` — *moved*. Verbatim; not recomputable from transactions.

#### `referral_rewards` → `referral_rewards` · **moved**

- **Owner → home:** own `referrer_id` (the balance owner).
- **Columns:** 7 of 8 move unchanged; exceptions:
  - `referred_user_id` — *moved*. Soft reference when referrer and referred live in different homes.

#### `affiliate_partners` → `affiliate_partners` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 11 of 12 move unchanged; exceptions:
  - `reviewed_by` — *moved*. Admin column, soft reference.

#### `affiliate_commissions` → `affiliate_commissions` · **moved**

- **Owner → home:** via `partner_id` → `affiliate_partners.user_id` (the balance owner; proposed, S03 confirms).
- **Columns:** 7 of 8 move unchanged; exceptions:
  - `buyer_user_id` — *moved*. Soft reference when the buyer lives in another home.

#### `affiliate_payouts` → `affiliate_payouts` · **moved**

- **Owner → home:** via `partner_id` → `affiliate_partners.user_id`.
- **Columns:** 8 of 10 move unchanged; exceptions:
  - `details` — *moved*. Payout recipient details: sensitive personal data.
  - `status` — *moved*. Verbatim: a `requested` payout already reduces the available balance.

#### `payment_routes` → `payment_routes` · **moved**

- **Owner → home:** platform catalog (R12).
- **Columns:** 7 of 8 move unchanged; exceptions:
  - `updated_by` — *moved*. Admin column, soft reference.
- Production rows decide which acquirers are live; the seed enables `tbank`, `lava`, `lava_paypal` and disables `cloudpayments`.

#### `exchange_rates` → `exchange_rates` · **moved**

- **Owner → home:** platform catalog (R12). Owned by F6 ([ADR 0036](../adr/0036-exchange-rate-owned-by-platform-services.md)).
- **Columns:** all 5 move unchanged.
- Append-only CBR history; money rows already snapshot the rate they used.

#### `usage_events` → `usage_events` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** 8 of 10 move unchanged; exceptions:
  - `created_at` — *transformed*. Partition key: monthly partitions per §8.2.
  - `session_id` — *moved*. Soft reference, unique: one tombstone per deleted meeting.
- Tombstones of deleted meetings; they feed the lifetime Free quota. Dropping a partition would re-open spent minutes, so the table is exempt from partition-drop retention (U-10, ADR 0007).

### 5.3 S04 — Meetings

#### `sessions` → `sessions` · **transformed**

- **Owner → home:** own `user_id`.
- **Rows:** rows with `user_id IS NULL` resolve to no owner and go to the orphan report (R11).
- **Columns:** 11 of 15 move unchanged; exceptions:
  - `status` — *moved*. `active`, `completed`, `failed`; `paused` is never written.
  - `latest_run_id` — *moved*. Soft reference to `meeting_processing_runs`.
  - `ephemeral` — *moved*. No-logs meetings carry no transcript; leftover content is a defect to report.
  - `client_device_id` — *moved*. Patterns `import-<uuid>`, `video-meeting`, `room-<id>` are kept.
- **New in v2:** `org_id` — NULL (R3).
- **New in v2:** `access` — The personal default defined by S02 (R3).
- **New in v2:** `indexed_upto_seq` — 0, so the v2 indexer rebuilds the meeting windows (R7).

#### `transcript_segments` → `transcript_segments` · **transformed**

- **Owner → home:** via `session_id` → `sessions.user_id`.
- **Columns:** 9 of 15 move unchanged; exceptions:
  - `started_at` — *transformed*. Kept at microsecond precision; partition key of the monthly partitions (§8.1).
  - `checksum` — *moved*. Verbatim: two formulas coexist (`sha256(text)` for live lines, `sha256(speaker|start_ms|text)` for canonical ones); it is the re-processing idempotency key.
  - `text` — *moved*. Verbatim; user edits overwrote it in place and are indistinguishable from originals.
  - `run_id` — *moved*. NULL = draft or legacy line, set = canonical line.
  - `speaker_label` — *moved*. Denormalised display name; renames were written to every row.
  - `created_at` — *moved*. Second ordering key for `seq`; NULLs get `started_at` (R10).
- **New in v2:** `seq` — Derived: `row_number() OVER (PARTITION BY session_id ORDER BY started_at, created_at, id)`, starting at 1 (T-1).
- The draft has no `seq`; v2 identity is `(session_id, seq)` (§8.1).
- The FK to `sessions` has no ON DELETE: load after `sessions`, delete before.

#### `meeting_speakers` → `meeting_speakers` · **moved**

- **Owner → home:** via `session_id` → `sessions.user_id`.
- **Columns:** 11 of 14 move unchanged; exceptions:
  - `identity_status` — *moved*. `confirmed`, `rejected` and `manual` sources are user decisions.
  - `person_entity_id` — *moved*. Soft reference to `pcg_entities`.
  - `user_id` — *moved*. Denormalised owner, no FK.

#### `meeting_notes` → `meeting_notes` · **moved**

- **Owner → home:** via `session_id` → `sessions.user_id`.
- **Columns:** 6 of 9 move unchanged; exceptions:
  - `draft_markdown` — *moved*. User content.
  - `enhanced_markdown` — *moved*. AI output; copied, never regenerated (costly and non-deterministic).
  - `template_id` — *moved*. String: a built-in key or a `meeting_templates.id`.

#### `meeting_note_action_items` → `meeting_note_action_items` · **moved**

- **Owner → home:** via `note_id` → `meeting_notes` → `sessions.user_id`.
- **Columns:** 6 of 8 move unchanged; exceptions:
  - `done` — *moved*. User decision on AI output.
  - `source_segment_id` — *moved*. Soft reference, may dangle.

#### `meeting_map_nodes` → `meeting_map_nodes` · **moved**

- **Owner → home:** via `session_id` → `sessions.user_id`.
- **Columns:** 9 of 12 move unchanged; exceptions:
  - `origin` — *moved*. `user` nodes are user content.
  - `edited` — *moved*. An edited AI node is a user decision.
  - `parent_node_id` — *moved*. Soft self-reference, ids kept.
- The FK to `sessions` has no ON DELETE: load after `sessions`.

#### `meeting_folders` → `meeting_folders` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** all 10 move unchanged.
- **New in v2:** `org_id` — NULL (R3).
- **New in v2:** `access` — The personal default defined by S02 (R3).

#### `meeting_tags` → `meeting_tags` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 6 move unchanged.

#### `session_tags` → `session_tags` · **moved**

- **Owner → home:** via `session_id` → `sessions.user_id`.
- **Columns:** all 2 move unchanged.

#### `meeting_templates` → `meeting_templates` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 6 move unchanged.

#### `meeting_processing_runs` → `meeting_processing_runs` · **moved**

- **Owner → home:** via `session_id` → `sessions.user_id`.
- **Columns:** 20 of 26 move unchanged; exceptions:
  - `state` — *moved*. Unfinished runs at freeze are re-driven by the v2 sweep from this state.
  - `stage_state` — *moved*. JSONB `{stage: {status, attempt, duration_ms, error_code, finished_at, data}}`.
  - `audio_key` — *moved*. Pointer to a transient audio object (≤ 72 h); kept only while the object exists (section 6).
  - `raw_transcript_key` — *moved*. Same lifecycle as `audio_key`.
  - `audio_upload_id` — *moved*. An open multipart upload in the draft bucket cannot continue in v2; set to NULL and the run is failed for re-upload (T-3).
  - `user_id` — *moved*. Denormalised owner, no FK.

#### `meeting_workspace_impacts` → `meeting_workspace_impacts` · **moved**

- **Owner → home:** via `session_id` → `sessions.user_id`.
- **Columns:** 17 of 19 move unchanged; exceptions:
  - `status` — *moved*. Anything but `suggested` is a user decision.
  - `target_id` — *moved*. String soft reference to the changed object.

#### `meeting_result_shares` → `meeting_result_shares` · **moved**

- **Owner → home:** own `owner_id`.
- **Columns:** 9 of 12 move unchanged; exceptions:
  - `token` — *moved*. Verbatim: plaintext secret in public URLs.
  - `password_hash` — *moved*. Bcrypt, verbatim.
  - `visibility` — *moved*. `private | shared | public`, the same values as §7.
- The link resolves only while `owner_id = sessions.user_id`.

#### `meeting_share_comments` → `meeting_share_comments` · **moved**

- **Owner → home:** via `share_id` → `meeting_result_shares.owner_id`.
- **Columns:** all 6 move unchanged.
- Comments by anonymous third parties; no id or IP is stored.

#### `meeting_segment_embeddings` → no v2 table · **derived**

- **Owner → home:** via `segment_id` → `transcript_segments`.
- **Columns:** 6, none copied.
- Per-segment `vector(1536)` (`openai/text-embedding-3-small`). v2 indexes per-minute windows in Qdrant (§3, §8.1); rebuilt from `transcript_segments` by cursor (R7).

#### `meeting_import_jobs` → `meeting_import_jobs` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 9 move unchanged.
- A legacy projection of the run state that the import screen still reads; S04 may fold it into runs, then this becomes a transformation.

#### `prompt_executions` → `prompt_executions` · **transformed**

- **Owner → home:** via `session_id` → `sessions.user_id`.
- **Columns:** 6 of 9 move unchanged; exceptions:
  - `created_at` — *transformed*. Partition key: monthly partitions per §8.2; NULLs get the session's `started_at` (R10).
  - `token_usage` — *moved*. Two JSONB shapes coexist: `{prompt_tokens, completion_tokens, total_tokens}` and `{input, output, cached}`.
  - `prompt_id` — *moved*. FK to `prompt_templates`; a platform prompt in the EU home makes it a soft reference.
- Assistant answers inside a meeting (the meeting's model executions, §10). The FK to `sessions` has no ON DELETE.

### 5.4 S06 — Rooms

#### `streams` → `streams` · **moved**

- **Owner → home:** own `owner_id`.
- **Columns:** all 19 move unchanged.
- Broadcasts (stream as an entity); owned by S06 since D4. Live fields (`status=live`, `pinned_principal`) are reset by M2 if a stream is live at freeze.

#### `stream_members` → `stream_members` · **moved**

- **Owner → home:** via `stream_id` → `streams.owner_id`.
- **Columns:** all 9 move unchanged.

#### `stream_bans` → `stream_bans` · **moved**

- **Owner → home:** via `stream_id` → `streams.owner_id`.
- **Columns:** all 6 move unchanged.

#### `stream_chat_messages` → `stream_chat_messages` · **moved**

- **Owner → home:** via `stream_id` → `streams.owner_id`.
- **Columns:** 9 of 10 move unchanged; exceptions:
  - `deleted_at` — *moved*. Soft delete, kept.
- Viewers' messages, kept only when the stream has `save_chat`.

#### `stream_admissions` → `stream_admissions` · **dropped**

- **Owner → home:** via `stream_id` → `streams.owner_id`.
- **Columns:** 9, none copied.
- Waiting-room knocks with a 10-minute life; nothing survives the window.

#### `stream_requests` → `stream_requests` · **dropped**

- **Owner → home:** via `stream_id` → `streams.owner_id`.
- **Columns:** 9, none copied.
- Raised hands with a 20-minute life; nothing survives the window.

#### `rooms` → `rooms` · **moved**

- **Owner → home:** own `owner_id`.
- **Columns:** 12 of 14 move unchanged; exceptions:
  - `invite_token` — *moved*. Verbatim: plaintext secret in invitation links.
  - `lk_room_name` — *moved*. Verbatim: LiveKit room name `r-<hex>`.

#### `room_recordings` → `room_recordings` · **moved**

- **Owner → home:** own `owner_id`.
- **Columns:** 11 of 13 move unchanged; exceptions:
  - `s3_key` — *moved*. Verbatim; the same object is also pointed to by `storage_files.s3_key` (section 6, prefix O2).
  - `egress_id` — *moved*. Verbatim: dedup key of the LiveKit egress.

#### `video_admin_actions` → `video_admin_actions` · **moved**

- **Owner → home:** own `owner_id`.
- **Columns:** 10 of 12 move unchanged; exceptions:
  - `admin_email` — *moved*. Denormalised admin address, personal data.
  - `target_identity` — *moved*. LiveKit identity = a user id as text, no FK.
- Append-only audit of platform admins acting on rooms.

#### `room_whiteboards` → `room_whiteboards` · **moved**

- **Owner → home:** via `room_id` → `rooms.owner_id`.
- **Columns:** 7 of 8 move unchanged; exceptions:
  - `files` — *moved*. Embedded images as JSONB in the row (≤ 8 MB), not in object storage.

### 5.5 S07 — Knowledge and search

#### `knowledge_space` → `knowledge_space` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** 4 of 6 move unchanged; exceptions:
  - `used_bytes` — *moved*. Verbatim; load `knowledge_document` before the release-usage trigger exists, or the load decrements it (E-6).
  - `provisioned_at` — *dropped*. Onyx provisioning marker; Onyx is decommissioned and no code reads it.

#### `knowledge_source` → `knowledge_source` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** 9 of 12 move unchanged; exceptions:
  - `credential_ciphertext` — *moved*. Byte-for-byte; Fernet ring (R6).
  - `push_token_sha256` — *moved*. Verbatim: the raw Obsidian push token is not recoverable.
  - `config` — *moved*. `integration` is a soft reference to a Nango integration key.
- **New in v2:** `org_id` — NULL (R3).
- **New in v2:** `access` — The personal default defined by S02, if S07 makes sources the company-shared collections (R3).

#### `knowledge_document` → `knowledge_document` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** 13 of 15 move unchanged; exceptions:
  - `content_sha256` — *moved*. Verbatim, except on rows of a connected source whose bytes exist nowhere: cleared, so the source's next sync is not skipped as unchanged (T-4).
  - `original_retained_at` — *moved*. NULL means the draft never stored the bytes (Onyx-era uploads, vault notes kept as a fingerprint only).
- **New in v2:** `original_s3_key` — Where the bytes are, in this order (T-4): the computed key `knowledge-originals/{user_id.hex}/{content_sha256}` when `original_retained_at IS NOT NULL`; else the linked personal file (`storage_file_id`) when its object still exists and its sha-256 equals `content_sha256`, copied to that key; else NULL. A NULL row of a connected source is re-synced from it; a NULL manual upload stays as a document that needs re-uploading (U-11).

#### `knowledge_document_version` → `knowledge_document_version` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 19 of 22 move unchanged; exceptions:
  - `id` — *moved*. Verbatim: UUIDv5 over document, content, embedding model and parse build.
  - `document_id` — *moved*. Soft reference: `knowledge_document.id`, or `sessions.id` when `source_type='meeting'`.
  - `s3_key` — *moved*. Pointer to the original (prefixes O6, O7).
- Anchors the originals; nodes and chunks are re-derivable from it.

#### `knowledge_node` → `knowledge_node` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 11 move unchanged.
- Parsed text; the only copy of a document's text if its original object is lost, so it is moved rather than re-parsed.

#### `knowledge_chunk` → no v2 table · **derived**

- **Owner → home:** own `user_id`.
- **Columns:** 9, none copied.
- Chunks of `knowledge_node`; `id` is the Qdrant point id. Rebuilt by the v2 chunker and indexer; copying is allowed only if v2 keeps the draft chunker version (R7).

#### `knowledge_job` → no v2 table · **derived**

- **Owner → home:** own `user_id`.
- **Columns:** 10, none copied.
- Pipeline leases; v2 creates a job for every version not in `ready`/`failed`/`quarantined`.

#### `knowledge_retrieval_trace` → no v2 table · **dropped**

- **Owner → home:** own `user_id`.
- **Columns:** 8, none copied.
- Debug trace of searches (query hash, timings) meant to live days; no retention exists in the draft. No user-visible value.

#### `notes` → knowledge-base items of source `note` (S07 designs the table) · **transformed**

- **Owner → home:** own `user_id`; NULL = platform baseline note, whose fate S07 decides (FM-2), until then R12.
- **Columns:** 4 of 8 move unchanged; exceptions:
  - `content` — *transformed*. The authoritative text; stored as the item's original (O6 layout, keyed by its sha-256) and indexed by the v2 knowledge pipeline (R7).
  - `title` — *moved*. The item's name.
  - `file_path` — *transformed*. Kept as the item's external path; `/v1/kb*` and the server-folder watcher that used it are dropped (FM-2).
  - `tags` — *moved*. Kept as item metadata.
- **New in v2:** `org_id` — NULL (R3).
- **New in v2:** `access` — The personal default defined by S02 (R3).
- FM-2: notes become one source of the knowledge base on Qdrant; Leo keeps saving notes and live answers keep finding them. `id` is kept, so references from Leo stay valid.
- The only copy of the notes' text. Not `meeting_notes`.

#### `chunks` → no v2 table · **derived**

- **Owner → home:** via `note_id` → `notes.user_id` (no FK).
- **Columns:** 7, none copied.
- Legacy notes RAG; replaced by the knowledge pipeline, which chunks the migrated notes (FM-2, R7). Orphans of deleted notes are not carried (R11).

#### `embeddings` → no v2 table · **derived**

- **Owner → home:** via `chunk_id` → `chunks` → `notes.user_id` (no FK).
- **Columns:** 5, none copied.
- `vector(384)` of legacy chunks; rebuilt (R7).

#### `kb_link_edges` → no v2 table · **dropped**

- **Owner → home:** via `source_note_id` → `notes.user_id` (no FK).
- **Columns:** 5, none copied.
- Wikilink graph of legacy notes. FM-2 drops the notes link graph: no screen and no shipped client uses it. Derived from `notes`, so no user content is lost.

#### `pcg_entities` → `pcg_entities` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** 10 of 11 move unchanged; exceptions:
  - `confidence` — *moved*. 1.0 marks a person named by the user; a rebuild must not merge it down.
- Context graph; no code rebuilds it from sources, so it is authoritative.

#### `pcg_edges` → `pcg_edges` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** 12 of 14 move unchanged; exceptions:
  - `src_id` — *moved*. Varchar soft reference, paired with `src_kind`.
  - `dst_id` — *moved*. Varchar soft reference, paired with `dst_kind`.
- No unique constraint by design; closed edges are history.

#### `pcg_facts` → `pcg_facts` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** 29 of 32 move unchanged; exceptions:
  - `status` — *moved*. User decision once confirmed, completed, cancelled or uncertain.
  - `raised_count` — *moved*. Counter incremented in the DB; not recomputable.
  - `refuted_reason` — *moved*. Refutation group is a user decision; CHECK pairs it with `refuted_evidence`.
- Unique `(user_id, source_kind, source_id, dedup_key)` is the extraction idempotency anchor.

### 5.6 S08 — Storage

#### `storage_files` → `storage_files` · **moved**

- **Owner → home:** own `owner_id`.
- **Columns:** 10 of 14 move unchanged; exceptions:
  - `s3_key` — *moved*. Verbatim; `u-{owner_id[:8]}/{file_id}/{name}` (section 6, O1, O2).
  - `share_token` — *moved*. Verbatim: plaintext secret in public file links.
  - `share_password_hash` — *moved*. Bcrypt, verbatim.
  - `parent_id` — *moved*. Folder tree; parents load before children.

### 5.7 S09 — Agent (Leo)

> **Leo architecture, accepted on 2026-10-08** ([docs/design/leo/ARCHITECTURE.md](../design/leo/ARCHITECTURE.md) §10, ADR 0023–0033). The S09 slice plan revises the targets below: `memory_items` → `memory_facts` with a pgvector embedding (ADR 0030, ADR 0033); `proactive_nudges` → `agent_suggestions` with `suggestion_deliveries` and `suggestion_feedback` (ADR 0027); new tables without a draft source: `agent_threads`, `agent_messages`, `agent_runs`, `agent_actions`, `agent_decisions`, `proactive_triggers`, and the platform tables `decision_policies`, `decision_thresholds` (EU home). The Redis `agent:ckpt:*` keys stay dropped (U-5).

#### `user_contexts` → `user_contexts` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 6 move unchanged.
- Personal context text injected into Leo's system prompt.

#### `user_context_files` → `user_context_files` · **transformed**

- **Owner → home:** via `user_context_id` → `user_contexts.user_id`.
- **Columns:** 7 of 9 move unchanged; exceptions:
  - `storage_path` — *transformed*. Local-disk path → object in the bucket (ADR 0014); the column becomes `s3_key` (section 6, L2).
  - `extracted_text` — *moved*. Personal text.

#### `leo_personalization` → `leo_personalization` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** all 11 move unchanged.

#### `memory_items` → `memory_items` · **transformed**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** 10 of 12 move unchanged; exceptions:
  - `embedding` — *derived*. `vector(384)`, rebuilt from `text` by the v2 indexer (R7).
  - `text` — *moved*. The authoritative memory text.

#### `agent_audit_log` → `agent_audit` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** 13 of 14 move unchanged; exceptions:
  - `created_at` — *transformed*. Partition key: monthly partitions; table renamed `agent_audit` per §8.2.
- Append-only audit of agent write actions; `args` is redacted.

#### `agent_skills` → `agent_skills` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 13 move unchanged.
- Installed skills pinned to a commit; `body` is kept, not re-fetched.

#### `prompt_templates` → `prompt_templates` · **moved**

- **Owner → home:** own `user_id`; NULL = platform prompt (R12).
- **Columns:** all 14 move unchanged.
- Platform rows (`user_id IS NULL`) stay platform rows; they are never attributed to an admin.

#### `prompt_role_bindings` → no v2 table · **dropped**

- **Owner → home:** platform.
- **Columns:** 6, none copied.
- Dead: no reader or writer in the draft; roles resolve through `prompt_templates.role`. Platform configuration, no user data.

#### `prompt_skills` → `prompt_skills` · **moved**

- **Owner → home:** via `prompt_id` → `prompt_templates.user_id`.
- **Columns:** all 7 move unchanged.
- Links a prompt to skills; a platform prompt with an admin's skill crosses homes and becomes a soft reference.

#### `models_registry` → `models_registry` · **moved**

- **Owner → home:** platform catalog (R12).
- **Columns:** 20 of 22 move unchanged; exceptions:
  - `openrouter_model_id` — *moved*. Verbatim: referenced softly by costs, defaults and user choices.
  - `tier` — *moved*. Decides premium gating.

#### `model_defaults` → `model_defaults` · **moved**

- **Owner → home:** platform catalog (R12).
- **Columns:** all 6 move unchanged.

#### `model_role_assignments` → `model_role_assignments` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 9 of 10 move unchanged; exceptions:
  - `reasoning_enabled` — *moved*. NULL means the user never chose; never coerced to false.

#### `proactive_nudges` → `proactive_nudges` · **transformed**

- **Owner → home:** own `user_id` (no FK).
- **Rows:** only rows younger than the 90-day retention at cutover.
- **Columns:** 12 of 14 move unchanged; exceptions:
  - `feedback` — *moved*. User decision; negative feedback suppresses the kind.
  - `dedup_key` — *moved*. Verbatim, so old signals are not announced again.

#### `proactive_deliveries` → no v2 table · **dropped**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** 10, none copied.
- Per-channel delivery log that the draft never purges; in-flight deliveries expire and the feed keeps the nudge. No user-visible value.

#### `proactive_push_subscriptions` → `proactive_push_subscriptions` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** 7 of 9 move unchanged; exceptions:
  - `auth` — *moved*. Verbatim; valid only with the same VAPID key pair (R6).
  - `p256dh` — *moved*. Verbatim.

#### `proactive_mail_cursors` → `proactive_mail_cursors` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** all 7 move unchanged.
- Moving it avoids one re-scan of every connected mailbox.

#### `proactive_mail_watches` → `proactive_mail_watches` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** all 6 move unchanged.

#### `proactive_settings` → `proactive_settings` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** all 11 move unchanged.

### 5.8 S10 — MCP

#### `mcp_client_connections` → `mcp_client_connections` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** 23 of 29 move unchanged; exceptions:
  - `token_ciphertext` — *moved*. Byte-for-byte; Fernet ring (R6).
  - `oauth_access_ciphertext` — *moved*. Byte-for-byte.
  - `oauth_refresh_ciphertext` — *moved*. Byte-for-byte.
  - `stdio_env_ciphertext` — *moved*. Byte-for-byte.
  - `tools_digest` — *dropped*. No reader or writer in the draft.
  - `tools_cached_at` — *dropped*. No reader or writer in the draft.

#### `mcp_exposed_resources` → `mcp_exposed_resources` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 6 move unchanged.

#### `mcp_oauth_clients` → `mcp_oauth_clients` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 11 of 12 move unchanged; exceptions:
  - `client_id` — *moved*. CIMD URL or soft reference to `mcp_registered_clients.client_id`.

#### `mcp_registered_clients` → `mcp_registered_clients` · **moved**

- **Owner → home:** platform (R12).
- **Columns:** all 8 move unchanged.
- Dynamic client registrations kept by external clients in their own configuration; losing them breaks those clients.

#### `mcp_tokens` → `mcp_tokens` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 11 of 13 move unchanged; exceptions:
  - `token_hash` — *moved*. Sha-256, verbatim: raw tokens cannot be re-issued.
  - `parent_token_id` — *moved*. Soft reference.

### 5.9 S11 — Errands

#### `errands` → `errands` · **transformed**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** 10 of 12 move unchanged; exceptions:
  - `workflow_id` — *dropped*. Temporal id; v2 runs errands from the row (§12), Temporal is not carried (section 7.3).
  - `payload` — *moved*. `remind {text}` or `send_email {to, subject, body, provider?}`.
- `scheduled` rows are the user's open orders; overdue ones fire right after cutover.

### 5.10 S12 — Connectors and calendar

#### `oauth_accounts` → `oauth_accounts` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 15 of 18 move unchanged; exceptions:
  - `access_token_enc` — *moved*. Byte-for-byte; Fernet `fernet_key` without the previous-key ring (R6).
  - `refresh_token_enc` — *moved*. Byte-for-byte.
  - `id` — *moved*. Verbatim: `calendar_integrations` and `jira_links` reference it.
- Integration grants (Google, Microsoft, Jira), not sign-in identities.

#### `calendar_events` → `calendar_events` · **moved**

- **Owner → home:** own `owner_id`.
- **Columns:** 19 of 22 move unchanged; exceptions:
  - `external_id` — *moved*. Provider event id.
  - `session_id` — *moved*. FK to `sessions`, kept.
  - `meeting_room_id` — *moved*. FK to `rooms`, kept.

#### `calendar_event_moves` → `calendar_event_moves` · **moved**

- **Owner → home:** via `event_id` → `calendar_events.owner_id`.
- **Columns:** all 7 move unchanged.

#### `calendar_event_notifications` → `calendar_event_notifications` · **moved**

- **Owner → home:** via `event_id` → `calendar_events.owner_id`.
- **Columns:** 5 of 6 move unchanged; exceptions:
  - `recipient` — *moved*. Third-party email address.
- Dedup log; without it upcoming events re-send invitations and reminders.

#### `calendar_integrations` → `calendar_integrations` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 10 of 11 move unchanged; exceptions:
  - `caldav_password_enc` — *moved*. Byte-for-byte; Fernet (R6).

#### `calendar_sync_state` → `calendar_sync_state` · **moved**

- **Owner → home:** via `integration_id` → `calendar_integrations.user_id`.
- **Columns:** all 13 move unchanged.
- A row means "this calendar is selected": a user choice. Sync tokens avoid a full resync.

#### `calendar_watch_channels` → `calendar_watch_channels` · **transformed**

- **Owner → home:** via `integration_id` → `calendar_integrations.user_id`.
- **Columns:** 7 of 10 move unchanged; exceptions:
  - `channel_id` — *moved*. Verbatim: providers post with it.
  - `client_state` — *moved*. Verbatim: plaintext shared secret checked on every push.
  - `webhook_secret_enc` — *dropped*. No reader or writer in the draft.
- Push channels point to `public_base_url`; they stay valid only if the URL path is preserved (S-5).

#### `calendar_sync_notifications` → `calendar_sync_notifications` · **dropped**

- **Owner → home:** platform.
- **Columns:** 5, none copied.
- Seven-day dedup log of incoming pushes; nothing is in flight after the window. The bigint sequence restarts.

#### `external_event_mapping` → `external_event_mapping` · **moved**

- **Owner → home:** via `integration_id` → `calendar_integrations.user_id`.
- **Columns:** all 11 move unchanged.
- Identity map local ↔ external events with tombstones; losing it duplicates events on the next sync.

#### `connector_connections` → `connector_connections` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** 7 of 8 move unchanged; exceptions:
  - `connection_id` — *moved*. Verbatim: id inside the Nango schema (section 7.4).

#### `meeting_integrations` → `meeting_integrations` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 10 of 12 move unchanged; exceptions:
  - `credential_ciphertext` — *moved*. Byte-for-byte; Fernet ring (R6).
  - `refresh_token_ciphertext` — *moved*. Byte-for-byte.
- Push of notes and action items to Slack, Zapier, Notion.

#### `jira_links` → `jira_links` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 17 of 18 move unchanged; exceptions:
  - `id` — *moved*. Verbatim: the Jira webhook URL carries it and is its only authentication.

#### `jira_issue_links` → `jira_issue_links` · **moved**

- **Owner → home:** via `link_id` → `jira_links.user_id`.
- **Columns:** all 9 move unchanged.

### 5.11 S13 — Tracker

#### `tracker_projects` → `tracker_projects` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** all 9 move unchanged.

#### `tracker_statuses` → `tracker_statuses` · **moved**

- **Owner → home:** via `project_id` → `tracker_projects.user_id`.
- **Columns:** all 8 move unchanged.
- Load before `tracker_tasks` (FK RESTRICT).

#### `tracker_tasks` → `tracker_tasks` · **moved**

- **Owner → home:** via `project_id` → `tracker_projects.user_id`.
- **Columns:** all 10 move unchanged.

#### `tracker_labels` → `tracker_labels` · **moved**

- **Owner → home:** via `project_id` → `tracker_projects.user_id`.
- **Columns:** all 6 move unchanged.

#### `tracker_task_labels` → `tracker_task_labels` · **moved**

- **Owner → home:** via `task_id` → `tracker_tasks`.
- **Columns:** all 2 move unchanged.

### 5.12 S14 — Analytics

#### `analytics_events` → `analytics_events` · **transformed**

- **Owner → home:** own `user_id` (no FK); anonymous events by rule R12.
- **Columns:** 22 of 25 move unchanged; exceptions:
  - `ts` — *moved*. Partition key; v2 keeps monthly partitions and creates every month present in the data.
  - `user_id` — *transformed*. Cleared on events of anonymised accounts (U-6).
  - `country` — *moved*. Two-letter snapshot; also an input for the home question U-1.

#### `analytics_identity` → `analytics_identity` · **transformed**

- **Owner → home:** own `user_id` (no FK).
- **Rows:** rows of anonymised accounts are not migrated (U-6): the link would re-identify their cleared events.
- **Columns:** all 5 move unchanged.

#### `satisfaction_surveys` → `satisfaction_surveys` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** all 14 move unchanged.

#### `client_error_logs` → `client_errors` · **transformed**

- **Owner → home:** own `user_id`; anonymous reports by rule R12.
- **Columns:** 12 of 15 move unchanged; exceptions:
  - `created_at` — *transformed*. Partition key: monthly partitions; table renamed `client_errors` per §8.2.
  - `ip` — *moved*. Personal data.
  - `device_id` — *moved*. Stable device identifier.

### 5.13 S15 — Administration and support

#### `tickets` → `tickets` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 8 of 9 move unchanged; exceptions:
  - `number` — *moved*. Verbatim; the home sequence continues after the highest number (U-7).

#### `ticket_messages` → `ticket_messages` · **transformed**

- **Owner → home:** via `ticket_id` → `tickets.user_id`.
- **Columns:** 4 of 5 move unchanged; exceptions:
  - `author_user_id` — *moved*. Soft reference when the author (staff) lives in another home.
- **New in v2:** `author_kind` — `staff` if the author's `users.role` is `admin` at migration time, else `user`; the draft derives it by a join that breaks after anonymisation.

#### `ticket_attachments` → `ticket_attachments` · **moved**

- **Owner → home:** via `message_id` → `ticket_messages` → `tickets.user_id`.
- **Columns:** 7 of 8 move unchanged; exceptions:
  - `s3_key` — *moved*. Verbatim; the key holds no owner (section 6, O8).

#### `broadcasts` → `broadcasts` · **moved**

- **Owner → home:** platform (R12).
- **Columns:** all 12 move unchanged.
- Admin mass email, not the S05 broadcasts. `channel='telegram'` is a placeholder never sent.

#### `error_logs` → `error_logs` · **transformed**

- **Owner → home:** platform (R12).
- **Columns:** 6 of 7 move unchanged; exceptions:
  - `created_at` — *transformed*. Partition key: monthly partitions per §8.2.
- Upstream provider errors for the admin monitoring page; no user column.

### 5.14 S16 — Hub, downloads and remaining modules

#### `hubs` → `hubs` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** 9 of 11 move unchanged; exceptions:
  - `organisation_id` — *moved*. Soft reference to `pcg_entities`.
  - `tracker_project_id` — *moved*. Soft reference to `tracker_projects`.
- Kept or dropped with the hub module by the D4 decision; dropping is a user-data decision.

#### `hub_meetings` → `hub_meetings` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** 8 of 9 move unchanged; exceptions:
  - `addressed_by` — *moved*. `human` is a user decision a re-addressing must not overwrite.

#### `hub_rules` → `hub_rules` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Columns:** all 7 move unchanged.
- Remembered user corrections.

#### `hub_materials` → `hub_materials` · **moved**

- **Owner → home:** own `user_id` (no FK).
- **Rows:** rows whose `hub_id` no longer exists are orphans of the draft's `delete_hub` and go to the orphan report (R11).
- **Columns:** 8 of 9 move unchanged; exceptions:
  - `ref_id` — *moved*. String soft reference to a knowledge document or a storage file.

#### `app_builds` → `app_builds` · **transformed**

- **Owner → home:** platform (R12).
- **Columns:** 11 of 12 move unchanged; exceptions:
  - `storage_name` — *transformed*. Local-disk file name → object in the bucket under `platform/` (ADR 0014); the column becomes the object key (section 6, L1).
- Desktop installers uploaded by admins; the compute plane is stateless in v2 (§13.3), so no local disk.

### 5.15 F1 — Backend foundation (platform tables)

#### `outbox_messages` → `outbox_messages` · **dropped**

- **Owner → home:** platform.
- **Rows:** precondition: zero unpublished rows at freeze (the relay drains them); published rows are a 7-day delivery history.
- **Columns:** 12, none copied.
- v2 starts with an empty outbox and an empty `processed_events`. Payloads of `billing.payment.succeeded` carry email and name; they are not copied.

### 5.16 F6 — Platform services (FM-4)

#### `voice_sessions` → `voice_sessions` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** 11 of 13 move unchanged; exceptions:
  - `resume_of` — *dropped*. No reader or writer in the draft.
  - `provider_cost_id` — *dropped*. No reader or writer in the draft.
- Usage record per Gemini Live session, settled by voice metering (F6, FM-4); no audio or text.

#### `translation_session` → `translation_session` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** 16 of 18 move unchanged; exceptions:
  - `resume_of` — *dropped*. No reader or writer in the draft.
  - `provider_cost_id` — *dropped*. No reader or writer in the draft.
- Usage record per translated call direction, settled by voice metering (F6, FM-4); no audio or text.

#### `abuse_events` → `abuse_events` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 9 of 10 move unchanged; exceptions:
  - `note` — *moved*. Free text; holds the user's appeal.
- Append-only audit of LLM anti-abuse transitions.

#### `abuse_states` → `abuse_states` · **moved**

- **Owner → home:** own `user_id`.
- **Columns:** 6 of 7 move unchanged; exceptions:
  - `whitelisted` — *moved*. Admin decision, not derivable.

#### `provider_costs` → `provider_costs` · **transformed**

- **Owner → home:** own `user_id`.
- **Columns:** 18 of 23 move unchanged; exceptions:
  - `created_at` — *transformed*. Partition key: monthly partitions per §8.1; NULLs get `now()` and are counted (R10).
  - `prompt_execution_id` — *dropped*. Never written by any code.
  - `model_name` — *moved*. Soft reference to `models_registry.openrouter_model_id`; the weekly premium filter depends on it.
  - `cost_usd` — *moved*. Numeric(12,6).
  - `cost_rub` — *moved*. Numeric(12,2) at the snapshotted `exchange_rate_used`.
- One row per paid provider call; never deleted. The last 7 days decide the weekly premium budget (E-3).

---

## 6. Object storage

### 6.1 The draft

**The bucket.** One bucket (`s3_bucket`) holds everything, at endpoint `https://s3.timeweb.cloud`, default region `ru-1`. All S3 calls go through `services/storage/s3_client.py`, except LiveKit egress, which uploads recordings itself.

| Property | Draft behaviour |
|---|---|
| Addressing | Path-style |
| Uploads | Proxied through the API; there are no presigned uploads. Desktop audio uses server-side multipart |
| Downloads | Presigned GET only |
| Object metadata | `Content-Type` and `Content-Disposition` set at write; a copy must preserve both |
| Object operations | No `copy_object` anywhere |
| Lifecycle | No lifecycle rule, and no rule aborting incomplete multipart uploads, in the repository. Any rule on the Timeweb side is unknown |

**Prefixes.** The table follows the draft code. The owner prefix `u-{id[:8]}` holds only 8 hex characters of the owner id, so it can collide between users. The owner is always taken from the pointer row, never from the key.

| ID | Key template | Pointer | Content and life | Deleted with the account? | v2 destination |
|---|---|---|---|---|---|
| O1 | `u-{owner_id[:8]}/{file_id}/{name}` | `storage_files.s3_key` | Personal files, any type, ≤ 5 GB; immutable except text files edited in place; quota grace sweep | Yes | The bucket (ADR 0014); moved |
| O2 | `u-{owner_id[:8]}/rec-{recording_id.hex}/{lk_room}.mp4` | `room_recordings.s3_key` **and** `storage_files.s3_key` (same object) | Room recordings written by LiveKit egress; large; immutable | Yes | The bucket (ADR 0014); moved once, both pointers kept |
| O3 | `meetings/u-{user_id[:8]}/{run_id}/{name}` | `meeting_processing_runs.audio_key` (`audio_owned`) | Imported and desktop audio; deleted after the result commits, at most 72 h | **No** | Moved only for unfinished runs at `T0` (T-3) |
| O4 | `meetings/raw/{user_id[:8]}/{run_id}/transcript.json` | `meeting_processing_runs.raw_transcript_key` | Raw recognition output; same life as O3 | **No** | Same as O3 |
| O5 | `meetings/diarization/{user_id[:8]}/{run_id}/turns.json` | None; derived from user and run ids | Diarizer turns; same life as O3 | **No** | Same as O3; v2 stores an explicit pointer |
| O6 | `knowledge-originals/{user_id.hex}/{content_sha256}` | Computed from `knowledge_document.content_sha256` when `original_retained_at IS NOT NULL`; stored in `knowledge_document_version.s3_key` | Originals of documents and notes, and canonical meeting transcripts; content-addressed, immutable | Partly: transcript originals are not | The bucket (ADR 0014); moved; the pointer becomes the column `knowledge_document.original_s3_key`. Documents without bytes: T-4 |
| O7 | `knowledge-engine/{user_id.hex}/{version_id.hex}/{name}` | `knowledge_document_version.s3_key` | Uploads of the new knowledge engine; immutable | **No** | The bucket (ADR 0014); moved |
| O8 | `tickets/{file_id}/u-{file_id[:8]}/{file_id}/{name}` | `ticket_attachments.s3_key` | Support attachments ≤ 10 MB; orphan sweep after 24 h | Yes | The bucket (ADR 0014); moved |
| O9 | `exports/{user_id}/{YYYYMMDD-HHMMSS}.zip` | `data_export_jobs.s3_key` | Data-export archives; the link expires after 24 h, but the object is never deleted | **No** | Only archives still valid at `T0` move (D-4) |

**Local disk.** The v2 compute plane is stateless (§13.3), so none of these stay on disk.

| ID | Location | Pointer | Content | v2 destination |
|---|---|---|---|---|
| L1 | `builds_dir` (default `./data/builds`, volume `app_data`) / `{uuid}{ext}` | `app_builds.storage_name` | Desktop installers ≤ 500 MB, uploaded by admins | The bucket (ADR 0014), `platform/app-builds/{id}{ext}`; pointer rewritten |
| L2 | `user_context_dir` (default `./data/user_context`) / `{user_id}/{file_id}_{name}` | `user_context_files.storage_path` (absolute path) | Personal context files; not removed on account deletion | The bucket (ADR 0014); pointer becomes `s3_key` |
| L3 | `kb_dir` (volume `app_kb`, `/app/knowledge_base`) | None | Watched by a log-only handler; no code writes there | Dropped once M1 confirms it is empty on the copy; anything found is reported (U-4) |

### 6.2 v2 bucket and key layout

- **One bucket for both homes** ([ADR 0014](../adr/0014-one-object-store-in-russia.md), §4.1, §8.1): the draft's bucket on Timeweb `ru-1`. Keys do not name the home; the pointer row in the owner's home database does. Platform objects (L1) go under `platform/`. (The first version of this section had a bucket per home; changed by the owner on 2026-10-02.)
- **The pointer is the truth.** Every object is reachable from exactly one pointer column that stores the full key. The deletion registry (§14 rule 7) walks the pointers, so legacy keys need no owner prefix to be deletable.
- **Proposed layout for objects v2 writes** (S08 confirms it with an ADR):

  | Key | Content |
  |---|---|
  | `u/{user_id}/…`, `o/{org_id}/…` | Owner-scoped content, with the full owner id |
  | `transient/…` | Meeting audio, raw recognition output and export archives, with a lifecycle expiry of 3 days as a safety net behind explicit deletion |
  | `platform/…` | Platform objects; their pointers live in the EU home |

  A bucket rule aborts incomplete multipart uploads after 24 hours (§10, Upload).

### 6.3 How objects migrate

1. **Keys stay as they are.** *Decided (U-3, [ADR 0006](../adr/0006-draft-bucket-becomes-russian-home-bucket.md)):* migrated objects keep their draft keys. Re-keying gives users nothing, needs a copy and a pointer rewrite for every object, and risks loss.
2. **The draft's bucket is kept.** *Decided (U-3, [ADR 0006](../adr/0006-draft-bucket-becomes-russian-home-bucket.md)):* the v2 bucket — one for both homes since ADR 0014 — is the draft's bucket itself, since both are Timeweb `ru-1`, so no object moves at all. If a new bucket is used instead, objects are copied with identical keys and metadata. The copy runs before the window and catches up by `LastModified` inside it.
3. **Only referenced objects move.** An object is migrated only if a migrated pointer references it. Objects without a pointer are not carried. They come from failed writes, deletions that did not clean up (O3–O5, O7, O9), the knowledge "prefix cleanup" that does not exist, and staged ticket uploads. M1 lists them by prefix with counts and sizes (D-2, U-4).
4. **Transient prefixes are mostly empty.** O3–O5 move only for runs unfinished at `T0`. An open multipart upload cannot continue against a new system: its run is failed and the client re-uploads (T-3).

---

## 7. Redis, Valkey and other stateful services

### 7.1 Redis and Valkey

**The instance.** Production runs one managed Valkey 9.1. The settings `redis_cache_url`, `redis_state_url` and `redis_lock_url` fall back to `redis_url`, and TaskIQ uses `redis_url` directly. An optional local LRU container serves the cache role when `REDIS_CACHE_URL` is set. v2 replaces all of this with a managed EU Valkey plus a local LRU cache (§4.2), so nothing is copied key by key. Each family below is drained, re-seeded, carried or dropped.

| Key family | What it holds | At cutover |
|---|---|---|
| `whisperer:taskiq:s:{critical,default,bulk,meeting}`, legacy lists `whisperer:taskiq:{queue}` | Queued tasks, including transactional mail | Drained to empty before `T0` (R14). Work left undone is re-selected by v2 sweeps from database state |
| `whisperer:dlq:{queue}` | Failed task records (7 days) | Exported for review, then dropped |
| `pending_reg:{email}` | Sign-ups waiting for the email code (15 min); the only copy of their consent snapshot | Lost. Those people register again (U-5) |
| `social:flow:*`, `social:ticket:*`, `social:pending:*`, `oauth:state:*`, `mcp:oauth:code:*`, `mcp:connect:state:*` | In-flight sign-in and OAuth flows (≤ 10 min) | Lost; the flows restart |
| `agent:ckpt:*` | Leo dialogue checkpoints (24 h) | Dropped. §8.1 accepts the loss; a pending confirmation must be asked again (U-5) |
| `agent:secret:*`, `agent:act:claim:*` | One-shot credentials and claims of confirmed actions (60 s) | Dropped; R14 guarantees nothing is in flight |
| `rt:roll:{session_id}` | Transcript mirror for resuming a live meeting; the only copy for private meetings | None at `T0` if no meeting is live (R14) |
| `ticket_upload:{user_id}` | Attachments staged before a ticket message is sent (6 h) | Lost; the objects are swept (U-5) |
| `spend:{user}:d*`, `spend:{user}:m*`, `spend:global:d*`, `spend:global:h*` | Daily and monthly spend counters that enforce ceilings | Re-seeded in v2 from `provider_costs` for the current day, hour and month (E-3) |
| `ocr:pages:{user}:{YYYYMM}` | Monthly OCR page ceiling | Re-seeded from the OCR rows of `provider_costs` (E-3) |
| `spend:global:kill` | Admin emergency stop of AI spend | Value carried: v2 starts engaged if it was engaged |
| `whisperer:billing:expiry_notified:{sub}:{until}` | Dedup of subscription-expiry emails (400 days) | Carried, in the form S03 chooses (a database table is recommended). Otherwise every expiring subscriber is emailed again |
| `mail:campaign:{campaign}:{hash}` | Per-recipient dedup of admin mailings (7 days) | Dropped; no mailing may run across `T0` |
| `state:analytics:alert:*`, `state:analytics:digest:*` | Alert state and the weekly digest marker | Carried; otherwise accept one repeated digest |
| `abuse:{user}:*`, `memory:summary:*`, breakers, slots, presence, pub/sub, locks, rate limits, caches | Signal windows, derived summaries, coordination state | Dropped. Durable abuse state is in `abuse_states`; summaries are rebuilt nightly (R7) |

### 7.2 NATS JetStream

The draft relays outbox events to the stream `WHISPERER_EVENTS` (7 days) and keeps failed deliveries in `WHISPERER_DLQ` (30 days). v2 has no NATS: events go through the outbox and TaskIQ (§12).

At freeze, consumers are brought to zero lag (R14). The DLQ is exported for review. Nothing is migrated.

### 7.3 Temporal

Errands run as Temporal workflows that sleep until `run_at`. Temporal keeps its execution state in its own PostgreSQL. The `errands` table is the record of what users ordered. v2 runs due errands from rows through the scheduler (§12), so Temporal is not carried.

Order at freeze:

1. Copy the `errands` rows.
2. Cancel every workflow, so none fires against the frozen draft.
3. Decommission Temporal with the draft.

Overdue `scheduled` errands fire right after cutover. Duplicates are prevented by the status check and the nudge dedup key `errand:{id}`.

### 7.4 Nango

The `nango` schema in the production database holds the OAuth tokens and integration configurations of all connectors, encrypted with `NANGO_ENCRYPTION_KEY`. `connector_connections.connection_id` points into it. v2 runs one Nango per home with its state in that home's database (§4.2).

*Following §4.2 and U-1:*

- The schema is copied unchanged into the RU home database. The RU Nango gets the same encryption key and the same public URL and callback (`https://whisperer.one/nango/oauth/callback`).
- The EU Nango starts empty.
- Moving an account RU → EU must move its Nango connections as a step of the transfer saga (S01, S12). Otherwise transferred users re-consent.

### 7.5 Qdrant

The draft's knowledge engine indexes into the collection `knowledge` only when `QDRANT_URL` is set; it is dormant by default. Nothing is migrated: v2 rebuilds its index from sources (R7).

### 7.6 State held by third parties

These external systems refer to our ids and URLs, so the ids (R1) and the public URL paths must not change (S-5):

| Provider | What it holds that references us |
|---|---|
| Acquirers | lava subscriptions (parent contract = first transaction), saved cards keyed by `customer_key = user_id.hex`, open holds |
| Google and Microsoft calendars | Watch channels posting to `/v1/integrations/{google,microsoft}/notifications` |
| Jira | Webhooks posting to `/v1/jira/webhook/{link_id}` |
| External MCP servers | OAuth clients we registered with them |
| LiveKit | No state of ours beyond recordings already in S3 |

---

## 8. Risks and the verifications M1 runs

Every risky item names a check. M1 runs it on every rehearsal and on the real run. Any mismatch fails the run (M1 prompt, step 3). "Equal" means equal between the draft copy at `T0` and v2 after the load.

### 8.1 Money

| ID | What can go wrong | Verification |
|---|---|---|
| M-1 | A payment changes id, amount or status, or is lost or duplicated | Per `(currency, status, method, product_kind)`: count, `SUM(amount)` and `SUM(amount_rub)` equal. The sets of `id` and `external_id` are equal. `external_id` is unique in v2 |
| M-2 | A charge was sent but not recorded, so the next sweep charges again | Precondition: zero `auto_charge_attempts` in `charging` and reconciliation run after the last webhook. The set of `pending` transactions is equal and is reconciled with the acquirers after cutover |
| M-3 | The credit balance drifts or a grant replays | Per user: `subscriptions.premium_credit_usd` equal, and equal to the last ledger row's `balance_after_usd`. Ledger row count and `SUM(delta_usd)` per user equal. Exactly one `grant` row per successful credit-pack transaction |
| M-4 | A referral or affiliate balance changes | The draft formulas, run on both sides, give equal results: the referral balance per user, and the affiliate earnings and available balance per partner. The sets of statuses of rewards, commissions and payouts are equal |
| M-5 | Money stays held at an acquirer | The set of `card_bindings` with an open hold (`hold_ref` set, `hold_released_at` NULL) is equal and reported for release |
| M-6 | A saved card can no longer be charged | `rebill_id_ciphertext` and `customer_key` are byte-equal. At most one `active` method per user. Inside the v2 runtime, the number of active methods that decrypt equals the number of active methods; counts only, no plaintext |
| M-7 | A promo code is over-used | `used_count` is equal per code and within `max_uses`. A cross-check against the count of successful transactions with that code is reported |
| M-8 | Cost history is lost | Per user and month: count, `SUM(cost_usd)` and `SUM(cost_rub)` of `provider_costs` equal |

### 8.2 Entitlements

| ID | What can go wrong | Verification |
|---|---|---|
| E-1 | Paid time is lost or extended | Per user: tariff code, `status`, `expires_at` (exact), `auto_renew`, `renewal_provider`, `bonus_minutes` and `credits` equal. Segments `(tier_rank, tariff_code, remaining_days)` equal |
| E-2 | The minutes quota resets or double-counts | Per user, the draft formula gives equal minutes used on both sides: live sessions + `no_logs_minutes_used` + `ai_minutes_used` + `SUM(usage_events.minutes)`. `usage_events.session_id` stays unique |
| E-3 | Spend ceilings re-open | Per user, the 7-day premium spend computed from `provider_costs` is equal at `T0`. After start, the v2 daily, hourly and monthly spend counters and the OCR page counter are at least the values recomputed from `provider_costs` |
| E-4 | The entitlement decision changes | For every user, v2's entitlement function gives the same result as the draft's at `T0`: active, deadline with grace, granted tiers, limits |
| E-5 | Auto-renewal charges without consent, or stops | The set of active `auto_renew_consents` (`tariff_id`, `disclosed_amount`, `period_days`) is equal |
| E-6 | The knowledge quota counter is decremented by the load | `knowledge_space.used_bytes` is equal per user. The trigger is created after the load. The daily reconcile reports no correction on the first run |

### 8.3 Transcripts and meeting content

| ID | What can go wrong | Verification |
|---|---|---|
| T-1 | A line is lost or duplicated, or the order changes | Per session: equal row count. `seq` runs 1..n without gaps, and ordering by `seq` equals ordering by `(started_at, created_at, id)`. sha-256 over the ordered `text` values is equal. `checksum`, `run_id`, `speaker_label`, `speaker_idx`, `speaker_id` are equal per id. The set of session ids with content is equal |
| T-2 | User decisions on AI output are lost | Equal hashes of `draft_markdown` and `enhanced_markdown`. Equal `done` flags of action items. Equal `origin`, `edited` and parent links of map nodes. Equal `identity_status` of speakers. Equal non-`suggested` statuses of workspace impacts. Equal user-decision columns of `pcg_facts` (status, refutation group, raised counters) |
| T-3 | A meeting that was being processed never finishes | Every run unfinished at `T0` is either finished by v2 or marked failed with a visible reason within one sweep interval after start. Its audio objects (O3–O5) exist in the bucket, or the run is failed for re-upload |
| T-4 | A knowledge document has no content to index (risk raised by D4) | M1 classifies every `knowledge_document` by where its bytes are: a retained original (O6); its linked personal file, when the object exists and its sha-256 equals `content_sha256` (copied to the O6 key); its connected source (`source_id` set, re-synced by v2); nowhere. Counts per class are reported, and the last class goes to U-11. Every pointer of the first two classes resolves (F-1). Every migrated note has an original whose sha-256 matches its text |

### 8.4 Audit and logs

| ID | What can go wrong | Verification |
|---|---|---|
| A-1 | An append-only record is lost or altered | For `agent_audit_log`, `abuse_events`, `video_admin_actions` and `login_events`: equal id sets, `id` unique across partitions, and per owner equal first and last timestamps. The company audit (`org_audit_events`) has no draft source and starts empty |

### 8.5 Deletion state

| ID | What can go wrong | Verification |
|---|---|---|
| D-1 | A deleted account comes back | Equal number of anonymised accounts. None has a directory entry. None owns a CONTENT or ACCOUNT row in v2: the v2 post-deletion check (§16.4) reports zero leftovers for each |
| D-2 | Data the draft failed to delete is carried into v2 | Objects without a pointer, objects under O3–O5, O7, O9 and L2 of anonymised accounts, and Nango, calendar and MCP grants of anonymised accounts are not migrated. M1 lists them with counts and sizes for the owner (U-4) |
| D-3 | Orphans are silently dropped or silently carried | Per table, the number of orphans not migrated (R11) is reported and matches the owner-approved list |
| D-4 | An expired export archive is resurrected | Only `ready` exports with `expires_at > T0` and their objects move. The count of the rest is reported |

### 8.6 Tokens, sessions and secrets

| ID | What can go wrong | Verification |
|---|---|---|
| S-1 | Users and desktop clients are signed out | Live `refresh_sessions` (`id`, `current_jti`, `prev_jti`, `expires_at`) and `users.token_version` are equal. On the rehearsal, a refresh token issued by the draft copy before `T0` rotates successfully in v2, and a draft access token is accepted until it expires |
| S-2 | Sign-in finds the wrong home or no account | One directory entry per non-anonymised account. `email_hmac` is unique, so normalised-email collisions are zero. Each entry's home equals its user's home. A sign-in smoke test passes for a sample per home |
| S-3 | A credential becomes unreadable | Every ciphertext column is byte-equal. Inside the v2 runtime, the count of rows whose ciphertext decrypts equals the row count, per column and per key ring (no plaintext leaves the process). Row counts of the `nango` schema are equal, and a Nango proxy call succeeds for a sample connection. A Web Push test succeeds for a sample subscription |
| S-4 | A public link stops working | `storage_files.share_token`, `meeting_result_shares.token`, `rooms.invite_token`, `users.ical_token` and the password hashes are equal. On the rehearsal, a sample of each link type resolves |
| S-5 | External callbacks stop arriving | `calendar_watch_channels` (`channel_id`, `client_state`, `resource_id`) and `jira_links.id` are equal. The v2 routes for calendar notifications, Jira webhooks, acquirer webhooks and the Nango callback answer at the draft paths (checked against the D1 contract) |
| S-6 | MCP clients lose access | Equal `mcp_tokens.token_hash`. Equal sets of `mcp_registered_clients` and consented `mcp_oauth_clients`. A personal MCP token from the copy authenticates against v2 on the rehearsal |

### 8.7 Files

| ID | What can go wrong | Verification |
|---|---|---|
| F-1 | A pointer leads nowhere, or an object is lost | Every migrated pointer resolves (HEAD) to an object of equal size, and an equal ETag where the provider is the same. Counts and bytes per prefix are equal. `users.storage_used_bytes` equals `SUM(storage_files.size)` per user, or the difference is reported |
| F-2 | A local-disk file is lost | Every L1 and L2 file exists as an object with equal sha-256. The pointer is rewritten. L3 is reported |

---

## 9. Volumes

**Current production: unknown.** Without access to the database there are no row counts. Known facts:

- production restarted empty on 2026-07-31;
- the database before that restart was 17 MB with 78 tables (draft notes in `docs/DB-MIGRATION-TIMEWEB.md`).

The order of magnitude at cutover is therefore small, and a full copy is expected to fit the 30-minute window (nfr-12). M1's first step on the copy measures it:

- exact `count(*)` and `pg_total_relation_size` per table;
- the size of the `nango` schema;
- object count and bytes per prefix O1–O9;
- file count and bytes in L1–L3.

`pg_stat` estimates are not used.

**Design point: estimates of growth per year at 10 000 DAU** (§3). These size the v2 tables; they are not migration volumes.

| Table | Driver | Rows per day | Size per year | Basis |
|---|---|---|---|---|
| `transcript_segments` | 400 lines per meeting-hour | 5.2 M | ≈ 1.9 TB | §3 |
| Meeting windows (vectors) | One per meeting-minute | 0.78 M | ≈ 437 GB | §3 |
| `org_audit_events` | ~200 actions per company | 20 k | ≈ 7 GB | §3 |
| `sessions` | 19 500 meetings per day | 19.5 k | ≈ 7 M rows, a few GB | §3 |
| `meeting_notes` | One per meeting, a few KB | 19.5 k | ≈ 35 GB | estimate |
| `prompt_executions` | ~10 answers per meeting, ~2 KB each | ≈ 0.2 M | ≈ 140 GB | estimate |
| `provider_costs` | ~30 paid calls per active user per day, ~0.4 KB | ≈ 0.3 M | ≈ 45 GB | estimate |
| `analytics_events` | ~30 events per user per day, ~0.5 KB | ≈ 0.3 M | ≈ 55 GB (24-month retention) | estimate; the draft's own figure is 30 events per user per day |
| `login_events` | ~2 per user per day | ≈ 20 k | ≈ 3 GB | estimate |
| `outbox_messages` | ≈ 4 events per meeting | ≈ 80 k | small (7-day retention) | §3 |
| Object storage | Files and recordings bounded by tariff quota; audio transient (≤ 72 h) | — | bounded by quotas | draft code |

**Re-embedding cost** (estimate). Rebuilding the vectors (R7) embeds every migrated transcript, note, memory and knowledge text once. The token count is about the number of characters divided by 4. At the current small volume the cost is negligible. M1 reports the measured character count before the rebuild starts.

**Duration** (estimate). A same-provider database copy runs at about 100 MB/s (§3 uses this rate for restores), so 30 minutes moves about 150 GB minus verification time. If the measured volume does not fit, M1 copies history before the window and catches up rows changed after a high-water mark inside it. The prompt of M1 requires this design.

---

## 10. Decisions for the user

The owner accepted every proposal on 2026-10-01. The decisions that change the architecture are recorded as ADRs and reflected in the target architecture: U-1 in [ADR 0004](../adr/0004-migrated-accounts-start-in-russian-home.md), U-2 and U-8 in [ADR 0005](../adr/0005-data-without-owner-in-eu-home.md), U-3 in [ADR 0006](../adr/0006-draft-bucket-becomes-russian-home-bucket.md), U-10 in [ADR 0007](../adr/0007-usage-tombstones-kept-for-lifetime-quota.md). The others are migration rules for M1 and for the slices named in section 5.

| ID | Question | Decision taken | Trade-off |
|---|---|---|---|
| U-1 | Home of existing accounts (R2) | All accounts go to the RU home at migration, where their data is today. Users outside Russia move to the EU home afterwards by the transfer saga, on a country they confirm | Nothing crosses a border at cutover, and the migration does not wait for the EU home, which does not exist yet. Until they move, EU users' primary data stays in Russia as it does today, against nfr-4 for them. The alternative, classifying by signals, may place people in the wrong home and needs the EU home ready at cutover |
| U-2 | Home of platform tables (R12) | The EU home, one copy, next to the directory; referenced by id without a foreign key | One writer and no cross-home writes. The cost is no FK integrity from the RU home, and one extra EU read per request (< 2 ms from the plane, cacheable). The alternative, the same rows in both homes, keeps the FKs but needs a sync for every admin edit. §4.2 and §6 now state this |
| U-3 | Object storage at cutover (section 6.3) | Use the draft bucket as the RU home bucket and keep draft keys | Zero object copies and no pointer rewrites. Legacy keys keep their 8-character owner prefix, so deletion must go by pointer, which the registry does anyway. The alternative is a new bucket plus a copy before the window and a catch-up |
| U-4 | Data not carried over (D-2, D-3, L3) | Do not carry: objects without a pointer; leftovers of deleted accounts (meeting audio, raw recognition, knowledge-engine originals, export archives, context files, external grants); orphan rows (R11); expired export archives. Also not carried, from section 5: the dropped tables and rows that hold personal data — `knowledge_retrieval_trace` (query hashes and timings), `proactive_deliveries`, `stream_admissions` and `stream_requests` (guest knocks and raised hands), dead `refresh_sessions` (IP, user agent), used or expired codes and reset tokens. Delete all of it from the draft storage when the draft is decommissioned, after M1's report | This finishes deletions users already asked for, and drops records with no further use. The counts are shown before anything is deleted |
| U-5 | Accepted in-flight losses at `T0` (section 7.1) | Accept the losses of sign-ups waiting for an email code, Leo dialogue state and pending confirmations, staged ticket attachments, and in-flight OAuth flows | They come from the maintenance window (≤ 30 min): people repeat a short action. Carrying them would need key-format compatibility between draft and v2 |
| U-6 | Analytics events of deleted accounts | Clear `user_id` on events of anonymised accounts during migration | Keeps aggregates and honours deletion (nfr-13). The draft deliberately keeps the id, so this changes draft behaviour |
| U-7 | Ticket numbers across homes | Keep numbers; the RU home continues the draft sequence; the EU sequence starts in a separate range (for example 900000) | Numbers stay unique and human-readable. The alternative is a home prefix in the number shown, a visible change |
| U-8 | Home of anonymous telemetry (R12) | EU home: `analytics_events` and `client_errors` rows without a user | It cannot be attributed to a person. It may still contain IP or device ids of Russian users, which is an accepted derived copy only if the legal review (§22) agrees |
| U-9 | Data of draft modules without a place in the architecture | **Decided by D4 on 2026-10-01** (FM-1, FM-2): hubs (S16), the whiteboard and broadcasts (S06) are kept and their data moves; legacy notes merge into the knowledge base (S07), and their link graph is dropped. Left to S07: the platform notes with an empty `user_id` | — |
| U-10 | Retention of `usage_events` | Keep tombstones for the life of the account, exempt from the partition-drop retention of §8.2 | The Free quota is lifetime minutes; dropping old tombstones would give deleted minutes back. §8.2 now states the exemption |
| U-11 | Knowledge documents whose content exists nowhere (T-4) | Keep each row as a document that needs re-uploading: its name stays in the knowledge list, and it is not indexed | Users see what is missing and can restore it. Dropping the rows would silently shrink their knowledge list. The counts come from M1 before the decision is applied |


---

## Appendix A. Draft schema at head 167

Generated from the database that the draft's migrations produced (see "How this was built" at the top). One block per table, in alphabetical order. `alembic_version` and the monthly partitions of `analytics_events` are omitted.

Notation:

- `NN`: NOT NULL. `= x`: server default.
- **Keys:** primary key, unique constraints, foreign keys with their delete rule, and checks.
- **Indexes:** secondary indexes. `unique` marks a unique index; the method is shown when it is not B-tree; partial indexes show their `WHERE`.

#### `abuse_events`

Columns: `id` uuid NN; `user_id` uuid NN; `at` timestamptz NN; `from_state` varchar(16) NN; `to_state` varchar(16) NN; `score` numeric(6,4) NN = '0'; `features` jsonb; `action` varchar(24) NN = 'none'; `actor` varchar(16) NN = 'system'; `note` text.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (at); (user_id).

#### `abuse_states`

Columns: `user_id` uuid NN; `state` varchar(16) NN = 'normal'; `score` numeric(6,4) NN = '0'; `whitelisted` boolean NN = false; `confirm_windows` integer NN = 0; `updated_at` timestamptz NN; `notified_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (user_id).

Indexes: (state).

#### `affiliate_commissions`

Columns: `id` uuid NN; `partner_id` uuid NN; `buyer_user_id` uuid NN; `transaction_id` uuid; `amount_rub` integer NN = 0; `status` varchar(16) NN = 'accrued'; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (buyer_user_id) → users(id) ON DELETE CASCADE; FK (partner_id) → affiliate_partners(id) ON DELETE CASCADE; FK (transaction_id) → transactions(id) ON DELETE SET NULL; PK (id); UNIQUE (buyer_user_id).

Indexes: (partner_id); (status).

#### `affiliate_partners`

Columns: `id` uuid NN; `user_id` uuid NN; `status` varchar(16) NN = 'pending'; `code` varchar(24); `revshare_percent` integer NN = 20; `reviewed_at` timestamptz; `reviewed_by` uuid; `note` varchar(255); `created_at` timestamptz = now(); `updated_at` timestamptz; `about` text; `blog_url` varchar(500).

Keys: FK (reviewed_by) → users(id) ON DELETE SET NULL; FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (code); UNIQUE (user_id).

Indexes: (status).

#### `affiliate_payouts`

Columns: `id` uuid NN; `partner_id` uuid NN; `amount_rub` integer NN = 0; `status` varchar(16) NN = 'requested'; `details` text NN = ''; `note` varchar(255); `processed_at` timestamptz; `processed_by` uuid; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (partner_id) → affiliate_partners(id) ON DELETE CASCADE; FK (processed_by) → users(id) ON DELETE SET NULL; PK (id).

Indexes: (partner_id); (status).

#### `agent_audit_log`

Columns: `id` uuid NN; `user_id` uuid NN; `thread_id` varchar(128) NN; `interrupt_id` varchar(64); `channel` varchar(16) NN; `tool_name` varchar(64) NN; `args` jsonb NN = '{}'; `status` varchar(16) NN; `error_code` varchar(64); `result` text; `latency_ms` integer; `approved_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (tool_name); (user_id); (user_id, created_at).

#### `agent_skills`

Columns: `id` uuid NN; `user_id` uuid NN; `source` varchar(16) NN; `repo` varchar(140) NN; `skill_path` varchar(255) NN; `ref` varchar(80) NN; `slug` varchar(80) NN; `description` text NN = ''; `body` text NN; `source_url` varchar(500) NN = ''; `installs` integer; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id, repo, skill_path).

Indexes: (user_id).

#### `analytics_events`

Columns: `ts` timestamptz NN; `event_id` uuid NN; `name` varchar(64) NN; `category` varchar(32) NN; `version` integer NN = 1; `anonymous_id` uuid NN; `user_id` uuid; `session_id` uuid; `source` varchar(8) NN; `platform` varchar(16) NN = ''; `app_version` varchar(32) NN = ''; `language` varchar(16) NN = ''; `country` varchar(2) NN = ''; `plan` varchar(16) NN = ''; `feature` varchar(32) NN = ''; `utm_source` varchar(64) NN = ''; `utm_medium` varchar(64) NN = ''; `utm_campaign` varchar(128) NN = ''; `referrer_domain` varchar(128) NN = ''; `sample_rate` float8 NN = '1'; `is_internal` boolean NN = false; `ts_client` timestamptz NN; `clock_skew_ms` bigint NN = '0'; `ingested_at` timestamptz NN = now(); `props` jsonb NN = '{}'.

Keys: PK (ts, event_id).

Indexes: CREATE INDEX ix_analytics_events_anon_ts ON ONLY public.analytics_events USING btree (anonymous_id, ts); CREATE INDEX ix_analytics_events_name_ts ON ONLY public.analytics_events USING btree (name, ts); CREATE INDEX ix_analytics_events_user_ts ON ONLY public.analytics_events USING btree (user_id, ts).

#### `analytics_identity`

Columns: `anonymous_id` uuid NN; `user_id` uuid NN; `source` varchar(16) NN; `linked_at` timestamptz NN = now(); `shared_device` boolean NN = false.

Keys: PK (anonymous_id, user_id).

Indexes: (user_id).

#### `app_builds`

Columns: `id` uuid NN; `platform` varchar(16) NN; `version` varchar(32) NN; `notes` text; `file_name` varchar(255) NN; `storage_name` varchar(255) NN; `size_bytes` bigint NN = '0'; `is_current` boolean NN = true; `published_at` timestamptz; `uploaded_by_user_id` uuid; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (uploaded_by_user_id) → users(id) ON DELETE SET NULL; PK (id).

Indexes: (is_current); (platform).

#### `auto_charge_attempts`

Columns: `id` uuid NN; `subscription_id` uuid NN; `renewal_period_key` varchar(64) NN; `status` varchar(16) NN = 'pending'; `attempt_count` integer NN = 0; `next_attempt_at` timestamptz; `amount` numeric(12,2) NN; `transaction_id` uuid; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (subscription_id) → subscriptions(id) ON DELETE CASCADE; FK (transaction_id) → transactions(id) ON DELETE SET NULL; PK (id); UNIQUE (subscription_id, renewal_period_key).

Indexes: (updated_at) WHERE ((status)::text = 'charging'::text); (subscription_id).

#### `auto_renew_consents`

Columns: `id` uuid NN; `user_id` uuid NN; `subscription_id` uuid NN; `tariff_id` uuid NN; `disclosed_amount` numeric(12,2) NN; `currency` varchar(3) NN = 'RUB'; `period_days` integer NN; `terms_version` varchar(32) NN; `consented_at` timestamptz NN; `revoked_at` timestamptz; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (subscription_id) → subscriptions(id) ON DELETE CASCADE; FK (tariff_id) → tariffs(id) ON DELETE RESTRICT; FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (subscription_id); (user_id).

#### `broadcasts`

Columns: `id` uuid NN; `channel` varchar(16) NN = 'email'; `audience` varchar(16) NN = 'all'; `subject` varchar(200) NN; `body` text NN; `status` varchar(16) NN = 'queued'; `recipients_count` integer NN = 0; `sent_count` integer NN = 0; `sent_at` timestamptz; `created_by_user_id` uuid; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (created_by_user_id) → users(id) ON DELETE SET NULL; PK (id).

Indexes: (status).

#### `calendar_event_moves`

Columns: `id` uuid NN; `event_id` uuid NN; `previous_start_at` timestamptz NN; `new_start_at` timestamptz NN; `source` varchar(16) NN; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (event_id) → calendar_events(id) ON DELETE CASCADE; PK (id).

Indexes: (event_id, created_at).

#### `calendar_event_notifications`

Columns: `id` uuid NN; `event_id` uuid NN; `kind` varchar(16) NN; `minutes_before` integer NN = '-1'; `recipient` varchar(320) NN; `sent_at` timestamptz NN = now().

Keys: FK (event_id) → calendar_events(id) ON DELETE CASCADE; PK (id); UNIQUE (event_id, kind, minutes_before, recipient).

Indexes: (event_id); (sent_at).

#### `calendar_events`

Columns: `id` uuid NN; `owner_id` uuid NN; `title` varchar(256) NN; `description` text; `start_at` timestamptz NN; `end_at` timestamptz NN; `event_type` varchar(16) NN; `location` varchar(1024); `participants` jsonb NN = '[]'; `reminders` jsonb NN = '[]'; `is_cancelled` boolean NN = false; `external_source` varchar(16); `recurrence_rule` varchar(512); `parent_event_id` uuid; `session_id` uuid; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `external_id` varchar(512); `external_etag` varchar(255); `external_updated_at` timestamptz; `meeting_room_id` uuid; `timezone` varchar(64).

Keys: FK (owner_id) → users(id) ON DELETE CASCADE; FK (parent_event_id) → calendar_events(id) ON DELETE CASCADE; FK (session_id) → sessions(id) ON DELETE SET NULL; FK (meeting_room_id) → rooms(id) ON DELETE SET NULL; PK (id).

Indexes: (description gin_trgm_ops) gin; (start_at) WHERE (reminders <> '[]'::jsonb); (external_source, external_id); (meeting_room_id); (owner_id); (owner_id, start_at); (parent_event_id); (session_id); (title gin_trgm_ops) gin.

#### `calendar_integrations`

Columns: `id` uuid NN; `user_id` uuid NN; `provider` varchar(30) NN; `enabled` boolean NN = true; `oauth_account_id` uuid; `caldav_url` varchar(1024); `caldav_username` varchar(255); `caldav_password_enc` bytea; `write_calendar_id` varchar(512); `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (oauth_account_id) → oauth_accounts(id) ON DELETE CASCADE; FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id, provider).

Indexes: (oauth_account_id); (user_id).

#### `calendar_sync_notifications`

Columns: `id` bigint NN = nextval('calendar_sync_notifications_id_seq'); `channel_id` varchar(128) NN; `resource_state` varchar(32); `msg_id` varchar(128) NN; `received_at` timestamptz NN = now().

Keys: PK (id); UNIQUE (channel_id, msg_id).

#### `calendar_sync_state`

Columns: `id` uuid NN; `integration_id` uuid NN; `external_calendar_id` varchar(512) NN; `is_write_target` boolean NN = false; `sync_token` text; `delta_link` text; `ctag` varchar(255); `last_full_sync_at` timestamptz; `last_incremental_sync_at` timestamptz; `last_error` text; `consecutive_failures` integer NN = 0; `backoff_until` timestamptz; `updated_at` timestamptz NN = now().

Keys: FK (integration_id) → calendar_integrations(id) ON DELETE CASCADE; PK (id); UNIQUE (integration_id, external_calendar_id).

Indexes: (integration_id).

#### `calendar_watch_channels`

Columns: `id` uuid NN; `integration_id` uuid NN; `external_calendar_id` varchar(512) NN; `provider` varchar(30) NN; `channel_id` varchar(128) NN; `resource_id` varchar(255); `expiration` timestamptz NN; `client_state` varchar(128) NN; `webhook_secret_enc` bytea; `created_at` timestamptz NN = now().

Keys: FK (integration_id) → calendar_integrations(id) ON DELETE CASCADE; PK (id); UNIQUE (channel_id).

Indexes: (expiration); (integration_id).

#### `card_bindings`

Columns: `id` uuid NN; `user_id` uuid NN; `provider` varchar(32) NN; `external_id` varchar(128) NN; `status` varchar(16) NN; `hold_ref` varchar(64); `hold_released_at` timestamptz; `completed_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (provider, external_id).

Indexes: (created_at) WHERE (((status)::text = 'pending'::text) OR ((hold_ref IS NOT NULL) AND (hold_released_at IS NULL))); (user_id).

#### `chunks`

Columns: `id` uuid NN; `note_id` uuid NN; `header_anchor` varchar(512); `content` text NN; `token_count` integer NN; `order_idx` integer NN; `created_at` timestamptz = now().

Keys: PK (id).

Indexes: (note_id).

#### `client_error_logs`

Columns: `id` uuid NN; `user_id` uuid; `platform` varchar(16) NN = 'macos'; `app_version` varchar(32); `os_version` varchar(32); `device_id` varchar(128); `level` varchar(16) NN = 'error'; `category` varchar(32) NN = 'general'; `code` varchar(64); `message` text NN; `stack` text; `context` jsonb; `ip` varchar(64); `created_at` timestamptz NN = now(); `occurred_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE SET NULL; PK (id).

Indexes: (category); (created_at); (device_id); (level); (platform); (user_id).

#### `connector_connections`

Columns: `id` uuid NN; `user_id` uuid NN; `provider_config_key` varchar(64) NN; `connection_id` varchar(128) NN; `broken` boolean NN = false; `connected_at` timestamptz NN = now(); `created_at` timestamptz NN = now(); `updated_at` timestamptz = now().

Keys: PK (id); UNIQUE (user_id, provider_config_key).

Indexes: (user_id).

#### `data_export_jobs`

Columns: `id` uuid NN; `user_id` uuid NN; `status` varchar(16) NN = 'pending'; `s3_key` varchar(1024); `size_bytes` bigint NN = '0'; `error` text; `finished_at` timestamptz; `expires_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz = now().

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id).

#### `desktop_auth_codes`

Columns: `id` uuid NN; `user_id` uuid NN; `code_hash` varchar(64) NN; `expires_at` timestamptz NN; `used_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (code_hash).

Indexes: (code_hash); (user_id).

#### `email_verification_codes`

Columns: `id` uuid NN; `user_id` uuid NN; `code_hash` varchar(64) NN; `expires_at` timestamptz NN; `attempts` integer NN = 0; `used_at` timestamptz; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (code_hash); (user_id).

#### `embeddings`

Columns: `id` uuid NN; `chunk_id` uuid NN; `embedding` vector(384) NN; `model_version` varchar(128) NN; `created_at` timestamptz = now().

Keys: PK (id); UNIQUE (chunk_id).

Indexes: (chunk_id); (embedding vector_cosine_ops) hnsw.

#### `errands`

Columns: `id` uuid NN; `user_id` uuid NN; `kind` varchar(32) NN; `status` varchar(16) NN = 'scheduled'; `run_at` timestamptz NN; `summary` varchar(300) NN; `payload` jsonb NN = '{}'; `workflow_id` varchar(128); `error` text; `finished_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz = now().

Keys: PK (id).

Indexes: (status, run_at); (user_id, status).

#### `error_logs`

Columns: `id` uuid NN; `level` varchar(16) NN = 'error'; `code` integer; `source` varchar(64) NN = 'llm'; `message` text NN; `context` jsonb; `created_at` timestamptz = now().

Keys: PK (id).

Indexes: (created_at); (level).

#### `exchange_rates`

Columns: `id` uuid NN; `currency_pair` varchar(16) NN = 'USD/RUB'; `rate` numeric(10,4) NN; `source` varchar(16) NN = 'cbr'; `fetched_at` timestamptz NN.

Keys: PK (id).

Indexes: (fetched_at).

#### `external_event_mapping`

Columns: `id` uuid NN; `integration_id` uuid NN; `calendar_event_id` uuid NN; `external_calendar_id` varchar(512) NN; `external_event_id` varchar(255) NN; `external_etag` varchar(255); `external_ical_uid` varchar(512); `direction` varchar(12) NN = 'bidirectional'; `last_synced_at` timestamptz; `deleted_at` timestamptz; `created_at` timestamptz NN = now().

Keys: FK (calendar_event_id) → calendar_events(id) ON DELETE CASCADE; FK (integration_id) → calendar_integrations(id) ON DELETE CASCADE; PK (id); UNIQUE (integration_id, external_event_id).

Indexes: (calendar_event_id); (external_ical_uid); (integration_id).

#### `hub_materials`

Columns: `id` uuid NN; `user_id` uuid NN; `hub_id` uuid NN; `kind` varchar(16) NN; `ref_id` varchar(128) NN; `title` varchar(300) NN; `session_id` uuid; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id); UNIQUE (hub_id, kind, ref_id).

Indexes: (hub_id); (user_id, kind, ref_id).

#### `hub_meetings`

Columns: `id` uuid NN; `user_id` uuid NN; `hub_id` uuid NN; `session_id` uuid NN; `primary` boolean NN = true; `addressed_by` varchar(16) NN; `confidence` float8 NN = '0'; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id); UNIQUE (hub_id, session_id).

Indexes: (hub_id); (user_id, session_id).

#### `hub_rules`

Columns: `id` uuid NN; `user_id` uuid NN; `hub_id` uuid NN; `kind` varchar(16) NN; `value` varchar(300) NN; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id); UNIQUE (user_id, kind, value).

Indexes: (user_id).

#### `hubs`

Columns: `id` uuid NN; `user_id` uuid NN; `name` varchar(200) NN; `kind` varchar(16) NN = 'client'; `tracker_project_id` uuid; `organisation_id` uuid; `archived` boolean NN = false; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `purpose` varchar(500); `success` varchar(500).

Keys: PK (id); UNIQUE (user_id, name).

Indexes: (user_id, archived).

#### `jira_issue_links`

Columns: `id` uuid NN; `link_id` uuid NN; `task_id` uuid NN; `issue_id` varchar(64) NN; `issue_key` varchar(64) NN; `known_remote_updated_at` timestamptz; `known_local_updated_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (link_id) → jira_links(id) ON DELETE CASCADE; FK (task_id) → tracker_tasks(id) ON DELETE CASCADE; PK (id); UNIQUE (link_id, issue_id); UNIQUE (link_id, task_id).

Indexes: (link_id).

#### `jira_links`

Columns: `id` uuid NN; `user_id` uuid NN; `oauth_account_id` uuid NN; `tracker_project_id` uuid NN; `cloud_id` varchar(64) NN; `jira_project_id` varchar(64) NN; `jira_project_key` varchar(32) NN; `jira_project_name` varchar(255) NN; `enabled` boolean NN = true; `webhook_id` varchar(64); `webhook_expires_at` timestamptz; `synced_through` timestamptz; `last_sync_at` timestamptz; `last_error` text; `consecutive_failures` integer NN = 0; `backoff_until` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (oauth_account_id) → oauth_accounts(id) ON DELETE CASCADE; FK (tracker_project_id) → tracker_projects(id) ON DELETE CASCADE; FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (tracker_project_id); UNIQUE (user_id, cloud_id, jira_project_id).

Indexes: (oauth_account_id); (user_id).

#### `kb_link_edges`

Columns: `id` uuid NN; `source_note_id` uuid NN; `target_note_id` uuid NN; `link_type` varchar(32) NN; `anchor_text` varchar(512).

Keys: PK (id).

Indexes: (source_note_id); (target_note_id).

#### `knowledge_chunk`

Columns: `id` uuid NN; `version_id` uuid NN; `user_id` uuid NN; `node_id` uuid NN; `parent_chunk_id` uuid; `content` text NN; `content_hash` varchar(64) NN; `token_count` integer NN; `language` varchar(8).

Keys: FK (node_id) → knowledge_node(id) ON DELETE CASCADE; FK (parent_chunk_id) → knowledge_chunk(id) ON DELETE SET NULL; FK (user_id) → users(id) ON DELETE CASCADE; FK (version_id) → knowledge_document_version(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id); (version_id).

#### `knowledge_document`

Columns: `id` uuid NN = gen_random_uuid(); `user_id` uuid NN; `name` varchar(500) NN; `size_bytes` bigint NN; `mime_type` varchar(200); `status` varchar(20) NN = 'pending'; `indexed_at` timestamptz; `last_error` text; `created_at` timestamptz NN = now(); `updated_at` timestamptz = now(); `source_id` uuid; `external_path` varchar(1000); `content_sha256` varchar(64); `storage_file_id` uuid; `original_retained_at` timestamptz.

Keys: FK (storage_file_id) → storage_files(id) ON DELETE SET NULL; FK (source_id) → knowledge_source(id) ON DELETE CASCADE; FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (source_id, external_path).

Indexes: (created_at) WHERE (original_retained_at IS NULL); (source_id); (user_id); unique (user_id, storage_file_id) WHERE (storage_file_id IS NOT NULL); unique (user_id, content_sha256) WHERE ((source_id IS NULL) AND (content_sha256 IS NOT NULL)).

#### `knowledge_document_version`

Columns: `id` uuid NN; `document_id` uuid NN; `user_id` uuid NN; `content_sha256` varchar(64) NN; `s3_key` varchar(1024) NN; `size_bytes` bigint NN; `mime_type` varchar(200); `source_type` varchar(32) NN; `language` varchar(8); `parser` varchar(64); `parser_version` varchar(32); `chunker_version` varchar(32); `embedding_model` varchar(128) NN; `embedding_dimensions` smallint; `retrieval_version` integer NN = 1; `state` varchar(20) NN = 'uploaded'; `indexed_at` timestamptz; `deleted_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `parse_build` varchar(32) NN = ''; `filename` varchar(500) NN = ''.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (document_id, content_sha256, embedding_model, parse_build).

Indexes: (state) WHERE ((state)::text <> 'ready'::text); (user_id, created_at).

#### `knowledge_job`

Columns: `id` uuid NN; `version_id` uuid NN; `user_id` uuid NN; `stage` varchar(24) NN = 'stored'; `attempts` smallint NN = '0'; `lease_until` timestamptz; `lease_holder` varchar(64); `last_error` text; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; FK (version_id) → knowledge_document_version(id) ON DELETE CASCADE; PK (id); UNIQUE (version_id).

Indexes: (stage, lease_until) WHERE ((stage)::text <> 'done'::text).

#### `knowledge_node`

Columns: `id` uuid NN; `version_id` uuid NN; `user_id` uuid NN; `parent_id` uuid; `kind` varchar(20) NN; `content` text NN; `section_path` text[] NN = '{}'; `page_start` integer; `page_end` integer; `ord` integer NN; `meta` jsonb NN = '{}'.

Keys: FK (parent_id) → knowledge_node(id) ON DELETE CASCADE; FK (user_id) → users(id) ON DELETE CASCADE; FK (version_id) → knowledge_document_version(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id); (version_id, ord).

#### `knowledge_retrieval_trace`

Columns: `id` uuid NN; `user_id` uuid NN; `query_hash` varchar(64) NN; `stages` jsonb NN = '{}'; `depth` varchar(8) NN; `depth_reason` varchar(32) NN; `total_ms` integer NN; `created_at` timestamptz NN = now().

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id, created_at).

#### `knowledge_source`

Columns: `id` uuid NN = gen_random_uuid(); `user_id` uuid NN; `kind` varchar(64) NN; `display_name` varchar(200) NN; `status` varchar(20) NN = 'pending'; `credential_ciphertext` bytea; `config` jsonb NN = '{}'; `last_indexed_at` timestamptz; `last_error` text; `created_at` timestamptz NN = now(); `updated_at` timestamptz = now(); `push_token_sha256` varchar(64).

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id, kind, display_name); UNIQUE (push_token_sha256).

Indexes: (user_id).

#### `knowledge_space`

Columns: `user_id` uuid NN; `used_bytes` bigint NN = '0'; `limit_override_bytes` bigint; `provisioned_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz = now().

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (user_id).

#### `leo_personalization`

Columns: `id` uuid NN; `user_id` uuid NN; `style` varchar(16) NN = 'default'; `warmth` varchar(8) NN = 'default'; `enthusiasm` varchar(8) NN = 'default'; `structure` varchar(8) NN = 'default'; `emoji` varchar(8) NN = 'default'; `instructions` text NN = ''; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `occupation` text NN = ''.

Keys: PK (id); UNIQUE (user_id).

#### `login_events`

Columns: `id` uuid NN; `user_id` uuid NN; `ip` varchar(64) NN; `user_agent` varchar(512); `outcome` varchar(16) NN = 'success'; `created_at` timestamptz = now().

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (created_at); (ip); (user_id).

#### `mcp_client_connections`

Columns: `id` uuid NN; `user_id` uuid NN; `name` varchar(120) NN; `url` varchar(2048) NN; `token_ciphertext` bytea; `enabled` boolean NN = true; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `transport` varchar(32) NN = 'streamable_http'; `protocol_version` varchar(32); `auth_kind` varchar(16) NN = 'bearer'; `oauth_issuer` varchar(512); `oauth_client_id` varchar(512); `oauth_scopes` text; `oauth_access_ciphertext` bytea; `oauth_refresh_ciphertext` bytea; `oauth_expires_at` timestamptz; `last_ok_at` timestamptz; `last_error_at` timestamptz; `last_error_code` varchar(64); `consecutive_failures` integer NN = 0; `disabled_reason` varchar(64); `tools_digest` varchar(64); `tools_cached_at` timestamptz; `oauth_token_endpoint` varchar(2048); `stdio_command` varchar(512); `stdio_args` jsonb; `stdio_env_ciphertext` bytea; `stdio_env_names` jsonb.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id).

#### `mcp_exposed_resources`

Columns: `id` uuid NN; `user_id` uuid NN; `key` varchar(40) NN; `enabled` boolean NN; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id, key).

Indexes: (user_id).

#### `mcp_oauth_clients`

Columns: `id` uuid NN; `user_id` uuid NN; `client_id` varchar(512) NN; `registration` varchar(16) NN = 'cimd'; `client_name` varchar(255); `redirect_uris` text; `scopes` text; `approved_at` timestamptz; `revoked_at` timestamptz; `last_used_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id, client_id).

Indexes: (user_id).

#### `mcp_registered_clients`

Columns: `id` uuid NN; `client_id` varchar(255) NN; `client_name` varchar(255); `redirect_uris` text NN; `scope` text; `last_used_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id); UNIQUE (client_id).

Indexes: (client_id).

#### `mcp_tokens`

Columns: `id` uuid NN; `user_id` uuid NN; `token_hash` varchar(64) NN; `label` varchar(120); `last_used_at` timestamptz; `expires_at` timestamptz; `revoked_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `scopes` text; `kind` varchar(16) NN = 'personal'; `oauth_client_id` uuid; `parent_token_id` uuid.

Keys: FK (oauth_client_id) → mcp_oauth_clients(id) ON DELETE CASCADE; FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (token_hash).

Indexes: (oauth_client_id); (token_hash); (user_id).

#### `meeting_folders`

Columns: `id` uuid NN; `user_id` uuid NN; `name` varchar(120) NN; `icon` varchar(40) NN = 'folder'; `color` varchar(16) NN = '#C8A02A'; `parent_id` uuid; `favorite` boolean NN = false; `position` integer NN = 0; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (parent_id) → meeting_folders(id) ON DELETE CASCADE; FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (parent_id); (user_id).

#### `meeting_import_jobs`

Columns: `id` uuid NN; `user_id` uuid NN; `session_id` uuid; `file_name` varchar(512) NN; `stage` varchar(16) NN = 'uploading'; `progress` float8 NN = '0'; `error` text; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (session_id) → sessions(id) ON DELETE CASCADE; FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (session_id); (user_id).

#### `meeting_integrations`

Columns: `id` uuid NN; `user_id` uuid NN; `type` varchar(16) NN; `credential_ciphertext` bytea NN; `target` varchar(256); `account_label` varchar(120); `push_notes` boolean NN = true; `push_action_items` boolean NN = true; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `refresh_token_ciphertext` bytea; `token_expires_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id, type).

Indexes: (user_id).

#### `meeting_map_nodes`

Columns: `id` uuid NN; `session_id` uuid NN; `node_type` varchar(32) NN; `title` text NN; `start_offset_ms` integer; `end_offset_ms` integer; `parent_node_id` uuid; `confidence` float8; `created_at` timestamptz = now(); `origin` varchar(8) NN = 'ai'; `edited` boolean NN = false; `position` integer NN = 0.

Keys: FK (session_id) → sessions(id); PK (id).

Indexes: (parent_node_id); (session_id).

#### `meeting_note_action_items`

Columns: `id` uuid NN; `note_id` uuid NN; `text` text NN; `done` boolean NN = false; `source_segment_id` uuid; `position` integer NN = 0; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (note_id) → meeting_notes(id) ON DELETE CASCADE; PK (id).

Indexes: (note_id).

#### `meeting_notes`

Columns: `id` uuid NN; `session_id` uuid NN; `draft_markdown` text NN = ''; `enhanced_markdown` text; `template_id` varchar(128); `version` integer NN = 0; `last_authoring_client` varchar(16) NN = 'web'; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (session_id) → sessions(id) ON DELETE CASCADE; PK (id); UNIQUE (session_id).

Indexes: (draft_markdown gin_trgm_ops) gin; (enhanced_markdown gin_trgm_ops) gin; (session_id).

#### `meeting_processing_runs`

Columns: `id` uuid NN; `session_id` uuid NN; `user_id` uuid NN; `state` varchar(24) NN = 'created'; `source` varchar(16) NN; `idempotency_key` varchar(128) NN; `audio_key` varchar(1024); `audio_owned` boolean NN = true; `audio_mimetype` varchar(128); `audio_bytes` bigint; `audio_duration_ms` integer; `audio_expires_at` timestamptz; `audio_deletion_pending` boolean NN = false; `stage_state` jsonb NN = '{}'; `attempt` smallint NN = '0'; `last_error` text; `cancel_requested` boolean NN = false; `trace_id` varchar(32); `stt_provider` varchar(32); `stt_model` varchar(128); `processing_ms` integer; `completed_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `raw_transcript_key` varchar(1024); `audio_upload_id` varchar(256).

Keys: FK (session_id) → sessions(id) ON DELETE CASCADE; PK (id); UNIQUE (session_id, idempotency_key).

Indexes: (audio_expires_at) WHERE (audio_key IS NOT NULL); (updated_at) WHERE (audio_deletion_pending IS TRUE); (user_id, created_at); (session_id, created_at); (state, updated_at) WHERE ((state)::text <> ALL ((ARRAY['completed'::character varying, 'partially_completed'::character varying, 'abandoned'::character varying, 'cancelled'::character varying])::text[])).

#### `meeting_result_shares`

Columns: `id` uuid NN; `session_id` uuid NN; `owner_id` uuid NN; `token` varchar(64) NN; `visibility` varchar(8) NN = 'private'; `password_hash` varchar(255); `expires_at` timestamptz; `include_transcript` boolean NN = false; `include_speakers` boolean NN = false; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `comments_enabled` boolean NN = true.

Keys: FK (owner_id) → users(id) ON DELETE CASCADE; FK (session_id) → sessions(id) ON DELETE CASCADE; PK (id).

Indexes: (owner_id); unique (session_id); unique (token).

#### `meeting_segment_embeddings`

Columns: `segment_id` uuid NN; `session_id` uuid NN; `user_id` uuid NN; `embedding` vector(1536) NN; `created_at` timestamptz NN = now(); `model` varchar(128) NN.

Keys: FK (segment_id) → transcript_segments(id) ON DELETE CASCADE; PK (segment_id).

Indexes: (embedding vector_cosine_ops) hnsw; (user_id, session_id).

#### `meeting_share_comments`

Columns: `id` uuid NN; `share_id` uuid NN; `author_name` varchar(64) NN; `body` text NN; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (share_id) → meeting_result_shares(id) ON DELETE CASCADE; PK (id).

Indexes: (share_id, created_at).

#### `meeting_speakers`

Columns: `id` uuid NN; `session_id` uuid NN; `run_id` uuid NN; `user_id` uuid NN; `cluster_idx` smallint NN; `display_label` varchar(128) NN; `person_entity_id` uuid; `identity_status` varchar(16) NN = 'unknown'; `identity_confidence` float8; `identity_source` varchar(16); `total_ms` integer NN = 0; `segments_count` integer NN = 0; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (session_id) → sessions(id) ON DELETE CASCADE; PK (id); UNIQUE (run_id, cluster_idx).

Indexes: (user_id, person_entity_id) WHERE (person_entity_id IS NOT NULL); (session_id).

#### `meeting_tags`

Columns: `id` uuid NN; `user_id` uuid NN; `name` varchar(60) NN; `color` varchar(16) NN = '#7C5CFF'; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id); unique (user_id, lower((name)::text)).

#### `meeting_templates`

Columns: `id` uuid NN; `user_id` uuid NN; `name` varchar(120) NN; `sections` jsonb NN = '[]'; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id).

#### `meeting_workspace_impacts`

Columns: `id` uuid NN = gen_random_uuid(); `session_id` uuid NN; `run_id` uuid NN; `user_id` uuid NN; `target_kind` varchar(24) NN; `target_id` varchar(64); `operation` varchar(24) NN; `before_state` jsonb; `after_state` jsonb NN; `confidence` float8 NN; `status` varchar(16) NN = 'suggested'; `policy_decision` varchar(16) NN; `evidence_segment_id` uuid; `source_text` text NN = ''; `dedup_key` varchar(200) NN = ''; `applied_at` timestamptz; `applied_mutation_id` varchar(64); `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (run_id) → meeting_processing_runs(id) ON DELETE CASCADE; FK (session_id) → sessions(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id); (session_id, status); unique (run_id, target_kind, operation, dedup_key) WHERE (target_id IS NULL); unique (run_id, target_kind, target_id, operation) WHERE (target_id IS NOT NULL).

#### `memory_items`

Columns: `id` uuid NN; `user_id` uuid NN; `kind` varchar(16) NN; `scope` varchar(16) NN = 'agent'; `text` text NN; `embedding` vector(384) NN; `importance` float8 NN = '0.5'; `confirmations` integer NN = 0; `last_used_at` timestamptz NN = now(); `forgotten` boolean NN = false; `created_at` timestamptz NN = now(); `updated_at` timestamptz = now().

Keys: PK (id).

Indexes: (embedding vector_cosine_ops) hnsw; (user_id, scope, forgotten).

#### `model_defaults`

Columns: `id` uuid NN; `tariff_code` varchar(16) NN; `role` varchar(24) NN; `model_id` varchar(128) NN; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id); UNIQUE (tariff_code, role).

#### `model_role_assignments`

Columns: `id` uuid NN; `user_id` uuid NN; `role` varchar(32) NN; `temperature` numeric(3,2) NN = 0.7; `max_tokens` integer NN = 2048; `created_at` timestamptz = now(); `updated_at` timestamptz; `model_id` varchar(128) NN; `model_type` varchar(16) NN; `reasoning_enabled` boolean.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id, role).

#### `models_registry`

Columns: `id` uuid NN; `openrouter_model_id` varchar(128) NN; `provider` varchar(64) NN; `display` varchar(256) NN; `type` varchar(32) NN = 'chat'; `tier` varchar(16) NN; `capabilities` jsonb NN = '[]'; `context_window` integer; `pricing_input` numeric(12,6) NN = '0'; `pricing_output` numeric(12,6) NN = '0'; `enabled` boolean NN = true; `version` integer NN = 1; `created_by_user_id` uuid; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `description` text; `description_source` text; `description_i18n` jsonb NN = '{}'; `description_hash` varchar(64); `released_at` timestamptz; `reasoning` jsonb; `metrics` jsonb.

Keys: FK (created_by_user_id) → users(id) ON DELETE SET NULL; PK (id); UNIQUE (openrouter_model_id).

Indexes: (created_by_user_id); (openrouter_model_id).

#### `notes`

Columns: `id` uuid NN; `title` varchar(512) NN; `content` text NN; `tags` varchar[]; `file_path` varchar(1024) NN; `created_at` timestamptz = now(); `modified_at` timestamptz = now(); `user_id` uuid.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (file_path).

Indexes: (content gin_trgm_ops) gin; (title gin_trgm_ops) gin; (user_id).

#### `oauth_accounts`

Columns: `id` uuid NN; `user_id` uuid NN; `provider` varchar(30) NN; `external_account_id` varchar(255) NN; `display_name` varchar(255); `access_token_enc` bytea; `refresh_token_enc` bytea; `expires_at` timestamptz; `scopes` jsonb NN = '[]'; `status` varchar(20) NN = 'active'; `last_refreshed_at` timestamptz; `refreshing_since` timestamptz; `last_error` varchar(500); `consecutive_refresh_failures` integer NN = 0; `provider_metadata` jsonb; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `personal_data_retrieved_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id, provider, external_account_id).

Indexes: (user_id).

#### `outbox_messages`

Columns: `id` uuid NN; `type` varchar(128) NN; `version` integer NN = 1; `subject_id` uuid; `user_id` uuid; `correlation_id` varchar(64); `payload` jsonb NN; `occurred_at` timestamptz NN = now(); `published_at` timestamptz; `available_at` timestamptz NN = now(); `attempts` integer NN = 0; `last_error` text.

Keys: PK (id).

Indexes: (published_at); (available_at, id) WHERE (published_at IS NULL).

#### `password_reset_tokens`

Columns: `id` uuid NN; `user_id` uuid NN; `token_hash` varchar(64) NN; `expires_at` timestamptz NN; `used_at` timestamptz; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (token_hash).

Indexes: (token_hash); (user_id).

#### `payment_routes`

Columns: `id` uuid NN; `scope` varchar(8) NN; `method` varchar(16) NN; `enabled` boolean NN = true; `position` integer NN = 0; `updated_by` uuid; `created_at` timestamptz NN = now(); `updated_at` timestamptz = now().

Keys: FK (updated_by) → users(id) ON DELETE SET NULL; PK (id); UNIQUE (scope, method).

#### `pcg_edges`

Columns: `id` uuid NN; `user_id` uuid NN; `src_kind` varchar(24) NN; `src_id` varchar(64) NN; `rel` varchar(32) NN; `dst_kind` varchar(24) NN; `dst_id` varchar(64) NN; `valid_from` timestamptz NN = now(); `valid_until` timestamptz; `confidence` float8 NN = '0.5'; `source_kind` varchar(24) NN; `source_id` varchar(64); `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id).

Indexes: (user_id, dst_kind, dst_id, rel); (user_id, src_kind, src_id, rel).

#### `pcg_entities`

Columns: `id` uuid NN; `user_id` uuid NN; `kind` varchar(24) NN; `name` varchar(300) NN; `norm_key` varchar(200) NN; `aliases` jsonb NN = '[]'; `confidence` float8 NN = '0.5'; `source_kind` varchar(24) NN; `source_id` varchar(64); `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id); UNIQUE (user_id, kind, norm_key).

Indexes: (user_id, kind).

#### `pcg_facts`

Columns: `id` uuid NN; `user_id` uuid NN; `kind` varchar(16) NN; `text` text NN; `dedup_key` varchar(200) NN; `status` varchar(16) NN = 'detected'; `confidence` float8 NN; `due_at` timestamptz; `counterparty_id` uuid; `project_id` uuid; `source_kind` varchar(24) NN; `source_id` varchar(64); `source_ref` varchar(64); `extracted_by` varchar(16) NN = 'leo'; `resolved_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `stance` varchar(16); `subject_entity_id` uuid; `valid_from` timestamptz; `valid_until` timestamptz; `superseded_by_id` uuid; `evidence_start_ms` integer; `evidence_end_ms` integer; `author_id` uuid; `raised_count` integer NN = 0; `raised_at` timestamptz; `raised_as` varchar(16); `refuted_reason` varchar(32); `refuted_evidence` text; `refuted_until` timestamptz; `refuted_as` varchar(16).

Keys: CHECK ((((refuted_reason IS NULL) AND (refuted_evidence IS NULL)) OR ((refuted_reason IS NOT NULL) AND (refuted_evidence IS NOT NULL) AND (length(btrim(refuted_evidence)) > 0)))); PK (id); UNIQUE (user_id, source_kind, source_id, dedup_key).

Indexes: (user_id, author_id) WHERE (author_id IS NOT NULL); (user_id, due_at); (user_id, kind, status); (user_id, subject_entity_id, valid_from) WHERE (stance IS NOT NULL); (user_id, refuted_until) WHERE (refuted_reason IS NOT NULL).

#### `premium_credit_ledger`

Columns: `id` uuid NN; `user_id` uuid NN; `delta_usd` numeric(12,6) NN; `kind` varchar(16) NN; `bucket` varchar(16); `model_name` varchar(128); `transaction_id` uuid; `balance_after_usd` numeric(12,6) NN; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (transaction_id) → transactions(id) ON DELETE SET NULL; FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id, created_at).

#### `proactive_deliveries`

Columns: `id` uuid NN; `user_id` uuid NN; `nudge_id` uuid NN; `channel` varchar(24) NN; `status` varchar(16) NN = 'pending'; `attempts` integer NN = 0; `pushed_at` timestamptz; `last_error` varchar(200); `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id); UNIQUE (nudge_id, channel).

Indexes: (user_id, status).

#### `proactive_mail_cursors`

Columns: `id` uuid NN; `user_id` uuid NN; `integration` varchar(64) NN; `seen_until` timestamptz NN; `scanned_at` timestamptz NN; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id); UNIQUE (user_id, integration).

Indexes: (scanned_at).

#### `proactive_mail_watches`

Columns: `id` uuid NN; `user_id` uuid NN; `email` varchar(320) NN; `label` varchar(80) NN = ''; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id); UNIQUE (user_id, email).

Indexes: (user_id).

#### `proactive_nudges`

Columns: `id` uuid NN; `user_id` uuid NN; `kind` varchar(32) NN; `dedup_key` varchar(200) NN; `title` varchar(300) NN; `reason` text NN; `link` varchar(200); `created_at` timestamptz NN = now(); `read_at` timestamptz; `hold_until` timestamptz; `emailed_at` timestamptz; `evidence` jsonb; `feedback` varchar(20); `feedback_at` timestamptz.

Keys: PK (id); UNIQUE (user_id, dedup_key).

Indexes: (user_id, created_at).

#### `proactive_push_subscriptions`

Columns: `id` uuid NN; `user_id` uuid NN; `endpoint` text NN; `p256dh` varchar(128) NN; `auth` varchar(64) NN; `label` varchar(120) NN = ''; `last_push_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: PK (id); UNIQUE (endpoint).

Indexes: (user_id).

#### `proactive_settings`

Columns: `id` uuid NN; `user_id` uuid NN; `level` varchar(16) NN = 'reserved'; `muted_kinds` varchar(32)[] NN = '{}'; `channels` varchar(16)[] NN = '{in_app}'; `quiet_from` time NN = '22:00:00'; `quiet_to` time NN = '08:00:00'; `quiet_enabled` boolean NN = true; `created_at` timestamptz NN = now(); `updated_at` timestamptz = now(); `notification_preview` boolean NN = true.

Keys: PK (id); UNIQUE (user_id).

#### `promo_codes`

Columns: `id` uuid NN; `code` varchar(32) NN; `kind` varchar(16) NN = 'percent'; `value` integer NN; `max_uses` integer; `used_count` integer NN = 0; `is_active` boolean NN = true; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: CHECK (((max_uses IS NULL) OR (used_count <= max_uses))); PK (id).

Indexes: unique (code).

#### `prompt_executions`

Columns: `id` uuid NN; `prompt_id` uuid; `session_id` uuid NN; `input_variables` jsonb; `output_text` text; `token_usage` jsonb; `latency_ms` integer; `user_feedback` varchar(16); `created_at` timestamptz = now().

Keys: FK (prompt_id) → prompt_templates(id); FK (session_id) → sessions(id); PK (id).

Indexes: (prompt_id); (session_id).

#### `prompt_role_bindings`

Columns: `id` uuid NN; `prompt_id` uuid NN; `role` varchar(32) NN; `is_default` boolean NN = false; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (prompt_id) → prompt_templates(id) ON DELETE CASCADE; PK (id); UNIQUE (prompt_id, role).

Indexes: unique (role) WHERE (is_default = true).

#### `prompt_skills`

Columns: `id` uuid NN; `prompt_id` uuid NN; `skill_id` uuid NN; `mode` varchar(8) NN = 'append'; `position` integer NN = 0; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (prompt_id) → prompt_templates(id) ON DELETE CASCADE; FK (skill_id) → agent_skills(id) ON DELETE CASCADE; PK (id); UNIQUE (prompt_id, skill_id).

Indexes: (prompt_id); (skill_id).

#### `prompt_templates`

Columns: `id` uuid NN; `name` varchar(256) NN; `version_tag` varchar(32) NN; `system_prompt` text NN; `user_prompt_template` text NN; `variable_schema` jsonb; `llm_config` jsonb; `is_active` boolean; `experiment_tag` varchar(128); `created_at` timestamptz = now(); `role` varchar(32); `tags` varchar(64)[] NN = '{}'; `is_archived` boolean NN = false; `user_id` uuid.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id, role, is_active).

#### `provider_costs`

Columns: `id` uuid NN; `user_id` uuid NN; `provider` varchar(32) NN; `model_name` varchar(128) NN; `role` varchar(32); `prompt_execution_id` uuid; `input_tokens` integer NN = 0; `output_tokens` integer NN = 0; `cost_usd` numeric(12,6) NN = '0'; `cost_rub` numeric(12,2) NN = '0'; `exchange_rate_used` numeric(10,4) NN = '0'; `created_at` timestamptz = now(); `updated_at` timestamptz; `latency_ms` integer; `session_id` uuid; `run_id` uuid; `feature` varchar(48); `unit` varchar(24); `units` integer NN = 0; `status` varchar(16) NN = 'ok'; `retry_no` integer NN = 0; `fallback_no` integer NN = 0; `estimated_cost_usd` numeric(12,6).

Keys: FK (prompt_execution_id) → prompt_executions(id) ON DELETE SET NULL; FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (feature, created_at) WHERE (feature IS NOT NULL); (provider, model_name, created_at); (user_id, created_at) WHERE ((retry_no > 0) OR (fallback_no > 0) OR ((status)::text <> 'ok'::text)); (run_id) WHERE (run_id IS NOT NULL); (session_id) WHERE (session_id IS NOT NULL); (user_id, created_at).

#### `recurring_payment_methods`

Columns: `id` uuid NN; `user_id` uuid NN; `customer_key` varchar(64) NN; `rebill_id_ciphertext` text; `card_mask` varchar(4); `card_exp` varchar(7); `status` varchar(16) NN = 'active'; `created_at` timestamptz = now(); `updated_at` timestamptz; `provider` varchar(16) NN = 'tbank'; `card_brand` varchar(16).

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id); unique (user_id) WHERE ((status)::text = 'active'::text).

#### `referral_rewards`

Columns: `id` uuid NN; `referrer_id` uuid NN; `referred_user_id` uuid NN; `transaction_id` uuid; `amount_rub` integer NN = 0; `status` varchar(16) NN = 'active'; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (referred_user_id) → users(id) ON DELETE CASCADE; FK (referrer_id) → users(id) ON DELETE CASCADE; FK (transaction_id) → transactions(id) ON DELETE SET NULL; PK (id); UNIQUE (referred_user_id).

Indexes: (referrer_id); (status).

#### `refresh_sessions`

Columns: `id` uuid NN; `user_id` uuid NN; `current_jti` varchar(64) NN; `prev_jti` varchar(64); `rotated_at` timestamptz; `expires_at` timestamptz NN; `revoked_at` timestamptz; `last_used_at` timestamptz; `device_label` varchar(128); `user_agent` varchar(256); `ip` varchar(64); `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id).

#### `room_recordings`

Columns: `id` uuid NN; `owner_id` uuid NN; `room_id` uuid NN; `egress_id` varchar(128); `s3_key` varchar(1024) NN; `status` varchar(16) NN = 'recording'; `size` bigint NN = '0'; `duration_seconds` integer; `storage_file_id` uuid; `session_id` uuid; `import_job_id` uuid; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (import_job_id) → meeting_import_jobs(id) ON DELETE SET NULL; FK (owner_id) → users(id) ON DELETE CASCADE; FK (room_id) → rooms(id) ON DELETE CASCADE; FK (session_id) → sessions(id) ON DELETE SET NULL; FK (storage_file_id) → storage_files(id) ON DELETE SET NULL; PK (id).

Indexes: unique (egress_id); (owner_id); (room_id).

#### `room_whiteboards`

Columns: `id` uuid NN; `room_id` uuid NN; `elements` jsonb NN = '[]'; `files` jsonb NN = '{}'; `version` integer NN = 1; `updated_by` varchar(128); `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (room_id) → rooms(id) ON DELETE CASCADE; PK (id).

Indexes: unique (room_id).

#### `rooms`

Columns: `id` uuid NN; `owner_id` uuid NN; `name` varchar(200) NN; `lk_room_name` varchar(128) NN; `status` varchar(12) NN = 'active'; `e2ee` boolean NN = false; `recording` boolean NN = false; `invite_token` varchar(64) NN; `max_participants` integer NN = 0; `closed_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `emptied_at` timestamptz; `started_at` timestamptz.

Keys: FK (owner_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (invite_token); UNIQUE (lk_room_name).

Indexes: (emptied_at) WHERE ((emptied_at IS NOT NULL) AND ((status)::text = 'active'::text)); (owner_id).

#### `satisfaction_surveys`

Columns: `id` uuid NN; `user_id` uuid NN; `status` varchar(16) NN = 'shown'; `score` integer; `answered_at` timestamptz; `language` varchar(8) NN = ''; `plan` varchar(32) NN = ''; `country` varchar(2) NN = ''; `platform` varchar(16) NN = 'other'; `gender` varchar(8) NN = 'unknown'; `gender_source` varchar(8) NN = 'none'; `is_internal` boolean NN = false; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: CHECK (((score IS NULL) OR ((score >= 1) AND (score <= 5)))); PK (id).

Indexes: (created_at, score) WHERE (score IS NOT NULL); (created_at); (user_id, created_at).

#### `session_tags`

Columns: `session_id` uuid NN; `tag_id` uuid NN.

Keys: FK (session_id) → sessions(id) ON DELETE CASCADE; FK (tag_id) → meeting_tags(id) ON DELETE CASCADE; PK (session_id, tag_id).

#### `sessions`

Columns: `id` uuid NN; `title` varchar(256) NN; `started_at` timestamptz NN; `ended_at` timestamptz; `status` varchar(20) NN = 'active'; `client_device_id` varchar(256) NN; `created_at` timestamptz = now(); `updated_at` timestamptz; `user_id` uuid; `ephemeral` boolean NN = false; `folder_id` uuid; `mcp_shared` boolean NN = false; `language` varchar(8); `source` varchar(16); `latest_run_id` uuid.

Keys: FK (folder_id) → meeting_folders(id) ON DELETE SET NULL; FK (user_id) → users(id) ON DELETE SET NULL; PK (id).

Indexes: (started_at) WHERE ((status)::text = 'active'::text); (folder_id); (user_id, started_at); (title gin_trgm_ops) gin; (user_id).

#### `storage_files`

Columns: `id` uuid NN; `owner_id` uuid NN; `name` varchar(500) NN; `is_folder` boolean NN = false; `parent_id` uuid; `s3_key` varchar(1024); `size` bigint NN = '0'; `mime_type` varchar(255); `share_token` varchar(64); `created_at` timestamptz NN = now(); `updated_at` timestamptz; `share_password_hash` varchar(255); `share_expires_at` timestamptz; `share_download_disabled` boolean NN = false.

Keys: FK (owner_id) → users(id) ON DELETE CASCADE; FK (parent_id) → storage_files(id) ON DELETE CASCADE; PK (id); UNIQUE (share_token).

Indexes: (name gin_trgm_ops) gin; (owner_id); (owner_id, parent_id); (parent_id); unique (share_token).

#### `stream_admissions`

Columns: `id` uuid NN; `stream_id` uuid NN; `knock_token` varchar(64) NN; `identity` varchar(128) NN; `display_name` varchar(100) NN = ''; `status` varchar(10) NN = 'pending'; `decided_at` timestamptz; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (stream_id) → streams(id) ON DELETE CASCADE; PK (id).

Indexes: (stream_id, status, created_at); unique (knock_token).

#### `stream_bans`

Columns: `id` uuid NN; `stream_id` uuid NN; `principal` varchar(128) NN; `display_name` varchar(100) NN = ''; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (stream_id) → streams(id) ON DELETE CASCADE; PK (id); UNIQUE (stream_id, principal).

#### `stream_chat_messages`

Columns: `id` uuid NN; `stream_id` uuid NN; `principal` varchar(128) NN; `author_name` varchar(100) NN = ''; `text` varchar(1000) NN; `from_stage` boolean NN = false; `pinned` boolean NN = false; `deleted_at` timestamptz; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (stream_id) → streams(id) ON DELETE CASCADE; PK (id).

Indexes: (stream_id, created_at); (principal).

#### `stream_members`

Columns: `id` uuid NN; `stream_id` uuid NN; `principal` varchar(128) NN; `display_name` varchar(100) NN = ''; `role` varchar(10) NN = 'speaker'; `on_air` boolean NN = true; `position` integer NN = 0; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (stream_id) → streams(id) ON DELETE CASCADE; PK (id); UNIQUE (stream_id, principal).

Indexes: (stream_id, "position").

#### `stream_requests`

Columns: `id` uuid NN; `stream_id` uuid NN; `principal` varchar(128) NN; `identity` varchar(128) NN; `display_name` varchar(100) NN = ''; `status` varchar(10) NN = 'pending'; `decided_at` timestamptz; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (stream_id) → streams(id) ON DELETE CASCADE; PK (id); UNIQUE (stream_id, principal).

Indexes: (stream_id, status, created_at).

#### `streams`

Columns: `id` uuid NN; `owner_id` uuid NN; `room_id` uuid NN; `title` varchar(200) NN; `description` text NN = ''; `status` varchar(12) NN = 'scheduled'; `started_at` timestamptz; `ended_at` timestamptz; `speaker_limit` integer NN = 10; `registered_only` boolean NN = false; `manual_admit` boolean NN = false; `chat_mode` varchar(10) NN = 'everyone'; `reactions_enabled` boolean NN = true; `requests_enabled` boolean NN = true; `save_chat` boolean NN = true; `stage_mode` varchar(12) NN = 'grid'; `pinned_principal` varchar(128); `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (owner_id) → users(id) ON DELETE CASCADE; FK (room_id) → rooms(id) ON DELETE CASCADE; PK (id).

Indexes: (owner_id, created_at); (owner_id); unique (room_id); (status).

#### `subscription_segments`

Columns: `id` uuid NN; `user_id` uuid NN; `tariff_id` uuid NN; `tariff_code` varchar(32) NN; `tier_rank` integer NN; `remaining_days` integer NN; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (tariff_id) → tariffs(id) ON DELETE RESTRICT; FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id); unique (user_id, tier_rank).

#### `subscriptions`

Columns: `id` uuid NN; `user_id` uuid NN; `tariff_id` uuid NN; `status` varchar(16) NN = 'active'; `started_at` timestamptz NN; `expires_at` timestamptz; `bonus_minutes` integer NN = 0; `credits` numeric(12,2) NN = '0'; `auto_renew` boolean NN = false; `created_at` timestamptz = now(); `updated_at` timestamptz; `premium_credit_usd` numeric(12,6) NN = '0'; `renewal_provider` varchar(16).

Keys: FK (tariff_id) → tariffs(id) ON DELETE RESTRICT; FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id).

Indexes: (expires_at) WHERE (auto_renew IS TRUE); (tariff_id).

#### `tariffs`

Columns: `id` uuid NN; `code` varchar(32) NN; `name` varchar(64) NN; `price_rub` integer NN = 0; `period_days` integer NN = 0; `minutes_limit` integer; `allow_knowledge_base` boolean NN = true; `allow_multiscreenshot` boolean NN = true; `allow_system_design` boolean NN = true; `allow_frontier_models` boolean NN = false; `is_active` boolean NN = true; `created_at` timestamptz = now(); `updated_at` timestamptz; `storage_limit_bytes` bigint; `price_usd` numeric(10,2) NN = '0'; `price_eur` numeric(10,2) NN = '0'; `knowledge_limit_bytes` bigint.

Keys: PK (id); UNIQUE (code).

Indexes: (code).

#### `ticket_attachments`

Columns: `id` uuid NN; `message_id` uuid NN; `filename` varchar(255) NN; `mime` varchar(128) NN; `size` bigint NN = '0'; `s3_key` varchar(1024) NN; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (message_id) → ticket_messages(id) ON DELETE CASCADE; PK (id).

Indexes: (message_id).

#### `ticket_messages`

Columns: `id` uuid NN; `ticket_id` uuid NN; `author_user_id` uuid; `body` text NN; `created_at` timestamptz = now().

Keys: FK (author_user_id) → users(id) ON DELETE SET NULL; FK (ticket_id) → tickets(id) ON DELETE CASCADE; PK (id).

Indexes: (ticket_id).

#### `tickets`

Columns: `id` uuid NN; `user_id` uuid NN; `subject` varchar(200) NN; `status` varchar(16) NN = 'open'; `created_at` timestamptz = now(); `updated_at` timestamptz; `user_last_read_at` timestamptz; `admin_last_read_at` timestamptz; `number` integer NN = nextval('ticket_number_seq').

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (number).

Indexes: (status); (user_id).

#### `tracker_labels`

Columns: `id` uuid NN; `project_id` uuid NN; `name` varchar(60) NN; `color` varchar(16) NN = '#94A3B8'; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (project_id) → tracker_projects(id) ON DELETE CASCADE; PK (id).

Indexes: (project_id); unique (project_id, lower((name)::text)).

#### `tracker_projects`

Columns: `id` uuid NN; `user_id` uuid NN; `name` varchar(120) NN; `key` varchar(10) NN; `description` text; `archived` boolean NN = false; `position` integer NN = 0; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id); unique (user_id, lower((key)::text)).

#### `tracker_statuses`

Columns: `id` uuid NN; `project_id` uuid NN; `name` varchar(60) NN; `category` varchar(20) NN = 'todo'; `color` varchar(16) NN = '#94A3B8'; `position` integer NN = 0; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: CHECK (((category)::text = ANY ((ARRAY['todo'::character varying, 'in_progress'::character varying, 'done'::character varying])::text[]))); FK (project_id) → tracker_projects(id) ON DELETE CASCADE; PK (id).

Indexes: (project_id); unique (project_id, lower((name)::text)).

#### `tracker_task_labels`

Columns: `task_id` uuid NN; `label_id` uuid NN.

Keys: FK (label_id) → tracker_labels(id) ON DELETE CASCADE; FK (task_id) → tracker_tasks(id) ON DELETE CASCADE; PK (task_id, label_id).

Indexes: (label_id).

#### `tracker_tasks`

Columns: `id` uuid NN; `project_id` uuid NN; `status_id` uuid NN; `title` varchar(200) NN; `description` text; `priority` varchar(10) NN = 'medium'; `position` integer NN = 0; `due_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: CHECK (((priority)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying, 'urgent'::character varying])::text[]))); FK (project_id) → tracker_projects(id) ON DELETE CASCADE; FK (status_id) → tracker_statuses(id) ON DELETE RESTRICT; PK (id).

Indexes: (description gin_trgm_ops) gin; (project_id); (status_id); (status_id, "position"); (title gin_trgm_ops) gin.

#### `transactions`

Columns: `id` uuid NN; `user_id` uuid NN; `tariff_id` uuid; `tariff_code` varchar(32) NN; `amount_rub` integer NN = 0; `method` varchar(16) NN = 'tbank'; `status` varchar(16) NN = 'pending'; `external_id` varchar(128); `paid_at` timestamptz; `created_at` timestamptz = now(); `updated_at` timestamptz; `referral_applied_rub` integer NN; `promo_code` varchar(32); `promo_discount_rub` integer NN = 0; `currency` varchar(3) NN = 'RUB'; `amount` numeric(12,2); `affiliate_code` varchar(24); `auto_renew_intent` boolean NN = false; `product_kind` varchar(16) NN = 'tariff'; `credit_spend_usd` numeric(12,6); `payment_url` varchar(1024).

Keys: FK (tariff_id) → tariffs(id) ON DELETE SET NULL; FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (paid_at) WHERE ((auto_renew_intent IS TRUE) AND ((status)::text = 'success'::text)); (status); (user_id); unique (external_id) WHERE (external_id IS NOT NULL).

#### `transcript_segments`

Columns: `id` uuid NN; `session_id` uuid NN; `speaker_label` varchar(128); `started_at` timestamptz NN; `duration_ms` integer NN; `text` text NN; `whisper_confidence` float8; `checksum` varchar(64) NN; `created_at` timestamptz = now(); `speaker_idx` smallint; `run_id` uuid; `ended_at` timestamptz; `language` varchar(8); `source` varchar(16); `speaker_id` uuid.

Keys: FK (session_id) → sessions(id); FK (speaker_id) → meeting_speakers(id) ON DELETE SET NULL; PK (id); UNIQUE (session_id, checksum).

Indexes: (run_id) WHERE (run_id IS NOT NULL); (session_id); (session_id, started_at); (speaker_id) WHERE (speaker_id IS NOT NULL); (text gin_trgm_ops) gin.

#### `translation_session`

Columns: `id` uuid NN; `user_id` uuid NN; `call_id` uuid; `direction` varchar(3) NN; `model` varchar(64) NN; `source_lang` varchar(16); `target_lang` varchar(16) NN; `voice` varchar(16) NN; `minted_at` timestamptz NN; `expire_at` timestamptz NN; `status` varchar(16) NN = 'minted'; `resume_of` uuid; `reported_at` timestamptz; `billed_tokens_in` bigint NN = '0'; `billed_tokens_out` bigint NN = '0'; `provider_cost_id` uuid; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (call_id); (status); (user_id).

#### `usage_events`

Columns: `id` uuid NN; `user_id` uuid NN; `session_id` uuid NN; `occurred_at` timestamptz NN; `ended` boolean NN = false; `minutes` numeric(10,2) NN = '0'; `ai_questions` integer NN = 0; `total_tokens` integer NN = 0; `created_at` timestamptz NN = now(); `updated_at` timestamptz NN = now().

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (user_id, occurred_at); unique (session_id).

#### `user_context_files`

Columns: `id` uuid NN; `user_context_id` uuid NN; `filename` varchar(256) NN; `mime_type` varchar(128) NN; `size_bytes` integer NN; `storage_path` varchar(512) NN; `extracted_text` text NN = ''; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (user_context_id) → user_contexts(id) ON DELETE CASCADE; PK (id).

#### `user_contexts`

Columns: `id` uuid NN; `user_id` uuid NN; `text` text NN = ''; `created_at` timestamptz = now(); `updated_at` timestamptz; `roles` varchar(32)[] NN = '{responses,coding,vision,system_design,agent}'.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id).

#### `user_identities`

Columns: `id` uuid NN; `user_id` uuid NN; `provider` varchar(16) NN; `subject` varchar(64) NN; `email_at_link` varchar(254); `last_login_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (provider, subject); UNIQUE (user_id, provider).

Indexes: (user_id).

#### `user_onboarding`

Columns: `id` uuid NN; `user_id` uuid NN; `status` varchar(16) NN = 'active'; `version` integer NN = 1; `current_step` varchar(48); `completed_steps` varchar(48)[] NN = '{}'; `done_actions` varchar(48)[] NN = '{}'; `started_at` timestamptz; `completed_at` timestamptz; `skipped_at` timestamptz; `created_at` timestamptz NN = now(); `updated_at` timestamptz; `audio_status` varchar(16) NN = 'new'.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id); UNIQUE (user_id).

Indexes: (created_at, status).

#### `users`

Columns: `id` uuid NN; `username` varchar(64); `password_hash` varchar(128); `is_active` boolean NN = true; `last_login_at` timestamptz; `created_at` timestamptz = now(); `updated_at` timestamptz; `email` varchar(254) NN; `phone` varchar(32); `role` varchar(16) NN = 'user'; `status` varchar(16) NN = 'active'; `referral_code` varchar(16); `referred_by_user_id` uuid; `email_verified` boolean NN; `avatar_url` text; `token_version` integer NN = 0; `language` varchar(8); `hotkeys` jsonb; `no_logs` boolean NN = false; `no_logs_minutes_used` float8 NN = '0'; `ical_token` varchar(64); `storage_used_bytes` bigint NN = '0'; `storage_limit_override_bytes` bigint; `storage_over_limit_since` timestamptz; `gender` varchar(8) NN = 'unset'; `marketing_consent` boolean NN = false; `consent_version` varchar(32); `consent_at` timestamptz; `consent_ip` varchar(64); `consent_user_agent` varchar(512); `ai_minutes_used` float8 NN = '0'; `timezone` varchar(64); `meeting_auto_tasks` boolean NN = false; `memory_enabled` boolean NN = true; `leo_voice_enabled` boolean NN = true; `leo_kb_search_enabled` boolean NN = true; `leo_connector_search_enabled` boolean NN = true; `leo_web_search_enabled` boolean NN = true; `appearance` jsonb.

Keys: FK (referred_by_user_id) → users(id) ON DELETE SET NULL; PK (id); UNIQUE (email); UNIQUE (ical_token); UNIQUE (referral_code).

Indexes: (email); (referral_code); (referred_by_user_id).

#### `video_admin_actions`

Columns: `id` uuid NN; `admin_id` uuid; `admin_email` varchar(320) NN; `action` varchar(32) NN; `lk_room` varchar(128) NN; `owner_id` uuid; `target_identity` varchar(128); `egress_id` varchar(128); `result` varchar(16) NN = 'ok'; `detail` varchar(500); `created_at` timestamptz NN = now(); `updated_at` timestamptz.

Keys: FK (admin_id) → users(id) ON DELETE SET NULL; FK (owner_id) → users(id) ON DELETE SET NULL; PK (id).

Indexes: (admin_id); (created_at); (lk_room, created_at).

#### `voice_sessions`

Columns: `id` uuid NN; `user_id` uuid NN; `model` varchar(64) NN; `minted_at` timestamptz NN; `expire_at` timestamptz NN; `status` varchar(16) NN = 'minted'; `resume_of` uuid; `reported_at` timestamptz; `billed_tokens_in` bigint NN = '0'; `billed_tokens_out` bigint NN = '0'; `provider_cost_id` uuid; `created_at` timestamptz = now(); `updated_at` timestamptz.

Keys: FK (user_id) → users(id) ON DELETE CASCADE; PK (id).

Indexes: (status); (user_id).
