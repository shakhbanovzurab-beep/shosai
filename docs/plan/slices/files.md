# files — slice plan

Prompt: [prompts/S-feature-slice.md](../prompts/S-feature-slice.md), launched through [BACKEND-next-step.md](../prompts/BACKEND-next-step.md). Status: [STATUS.md](../STATUS.md). Slice card: [SLICE_MAP.md §4.2.4](../SLICE_MAP.md#4-files).

`files` is the one path for bytes in Shosai: a person's File Manager (files, flat folders, "Use with Leo"), the presigned uploads every slice that takes bytes goes through, download links, the storage quota, and the file a person shares into a workspace or hands over to it. It comes in wave 1, after billing·entitlements, so that meetings, capture, Leo, knowledge, support and hubs are written against one upload path and one quota.

- **Status:** written on 2026-10-18 and approved by the owner the same day: FL-D1, FL-D3, FL-D4, FL-D6, FL-D7, FL-D8 as proposed, FL-D2 and FL-D5 with the owner's amendments (§2); the transfer port is recorded in workspaces' plan (step 9).
- **Philosophy check:** files live in one place; Leo and workspaces point to them and never copy them. A person never manages two storages and never re-uploads a file to share it. A lapsed plan stops new bytes at once and takes nothing away for 90 days, with three reminders; a deleted file can be brought back by support for a week. Upload and Undo are quiet; the only notices are the plain reason when a limit bites and the reminders before anything is removed.

---

## 1. Facts this plan rests on

### 1.1 Inputs

| Source | Fact |
|---|---|
| [SLICE_MAP](../SLICE_MAP.md) §4.2.4 | Scope: files and folders of a person or a workspace; presigned multipart uploads (§10) used by every slice that takes bytes (recordings, Leo attachments, ticket attachments, hub materials, workspace uploads); download URLs; the storage quota and `storage_used_bytes` (F-1); the "use with Leo" flags; transfer of a file to a workspace; deletion with Undo. Owns `storage_files` (O1), `uploads`; the S08 key-layout ADR. Routes `/v1/files/*`, `/v1/me/uploads*`, none native. Emits `files.uploaded`, `.deleted`, `.leo_use_changed`. Leo toolset `files`: search, read (digest), set "use with Leo" (W), move (W), delete (W, irreversible) |
| Target architecture | §4.1 rule 2 and ADR 0044: a bucket per home; §4.3: presigned upload and download, signature 15 min, the size limit in the signature; §6: bytes live in the bucket of the pointer's home, keys do not name the home, a transfer copies objects with identical keys before switching; §7: files are a resource with workspace access, a personal file is shared by a share record owned by workspaces, never copied; §8.1 File row: S3 object + `storage_files`, the pointer committed after the multipart upload completes, objects immutable, row deleted then object, orphans by lifecycle rules; §9 inv-11 (bytes only in the pointer's home bucket, reachable only through the pointer; the quota not exceeded), inv-14, inv-15, inv-17; §10 Upload: `POST /v1/me/uploads` → presigned part URLs, PUT to S3, `POST …/complete`, part replay overwrites, READY or REJECTED over size, abandoned uploads removed by lifecycle after 24 h; cursor pages, `Idempotency-Key` on retryable unsafe writes, one error envelope; §14 rules 1 (no S3 call inside a transaction), 7 (one registry over tables, prefixes and grants), 8 (timeouts, no DB session across storage calls), 13; §19: presigned uploads directly to the bucket, two-step upload, abandoned uploads removed by bucket rules |
| ADRs | 0044 (bucket per home, `CoreServices.objects[home]`/`uploads[home]`, `storage_unavailable` 503 for that home only); 0006 (draft keys kept, the pointer stores the full key, never an owner derived from a key, deletion through pointers, lifecycle rules on v2 prefixes only); 0015 (no `upload_fileobj`; presigned requests and the port's multipart); 0039 and 0053 (share records, levels, member withdrawal, workspace deletion saga keeps personal files with their owners); 0045 points 6–8 (a hidden account's data served to nobody; the account data registry; avatars outside the quota); 0054 (`file_manager_gb`, `knowledge_base_mb`) |
| Core and other slices | `core/storage`: `ObjectStorage` (put, open, head, delete, delete_many, list, `presign_get` with pinned content type and disposition, `presign_put` for an exact length), `MultipartUploads` (create, `presign_part` with its length, list_parts, complete, abort), `copy_objects`, keys checked, metrics with `home`; no upload table, no lifecycle helper. workspaces: `ShareableResource("file", …)` on `FeatureModule.shareable`, `ACCESS_POLICY` predicates inside the slice's query, `SHARE_RECORDS["file"]` maps a personal file to `workspace_knowledge_items` (`source_kind='personal'`, `file_id`), `AuditAction.FILE_TRANSFERRED`, events `workspaces.member.removed`, `.knowledge_item.*`, `.workspace.deleted`; the workspace-data registry (workspaces step 11) is not built yet. billing: `Entitlements.snapshot(home, user_id)` gives `file_manager_gb` and `knowledge_base_mb` (None unlimited, 0 not included; Free has 0 for both); no storage meter in billing. core: `AccountDataSpec` with prefixes, `copy_objects` for transfer, identity's handler as the reference |
| Cabinet ([frontend/](../../../frontend)) | `docs/file-manager-api.md` and `src/features/file-manager`: `GET /files` → `{folders, files}` newest first, no pagination or server search (search, filters and sort run on the client); `POST /files` multipart `files` (1–20, ≤ 2 GB each, 413/422), `folder_id`, `leo`; `PATCH /files/{id}` `{name?, folder_id?, starred?, leo?}`; `DELETE` final (the UI delays it behind an Undo toast); `POST /files/{id}/copy`, `/reindex` (409 when Leo does not use it), `/transfer {workspace_id}` (409 `shareFirst`); folders flat `{id, name, updated_at, leo}` with POST, PATCH, DELETE (its files move to the root). `FileItem {id, name, kind, content_type, size_bytes, folder_id, modified_at, starred, leo_readable, leo}`, `LeoUse {via: file \| folder, status: queued…indexed \| failed, progress, chunk_count, error}`; Leo-readable = one of 9 extensions and ≤ 50 MB; the Leo limit (409 `overLeoLimit`) sums the bytes of the files Leo uses against `knowledge_base_mb`. Names 1–120 characters, no slashes. No download, preview or storage meter on screen yet. `knowledge-base-api.md`: no file routes of its own (Knowledge uploads through `POST /files` with `leo=true`), one index per file, workspaces answer from the same vectors. Other uploaders: workspace knowledge uploads (10 × 25 MiB), Leo attachments (5 × 10 MiB), support attachments (5 × 10 MiB, `url`), hub materials (a file or a link), recordings (25 MiB), admin app builds (500 MiB); every one is a plain form POST to its slice today. Upgrade: `file_manager_gb` is storage, `knowledge_base_mb` the bytes Leo uses; a limit of 0 shows an upgrade screen |
| Native clients ([contracts/](../../../contracts/README.md)) | No `/v1/me/storage/*` or file route is native. The native uploads are meetings' audio routes (`/v1/me/sessions/{id}/audio/*`, server-side multipart, `{"detail": {"code": …}}`), owned by meetings, not files |

### 1.2 The draft, for lessons

Read in `/root/whisperer/backend/src/meetassist/` (`services/storage/*`, `api/me_storage.py`, `api/storage_public.py`, `core/share_ticket.py`, `tasks/maintenance.py`), spec 065, DATA_MAPPING §5.3, §6, F-1, S-4.

| Draft fact or incident | Rule in v2 |
|---|---|
| Uploads were proxied through the API and spooled to disk in full before any check; the per-file cap fell from 10 to 5 GB because of it (db3a205e1) | Bytes go straight to the bucket by presigned part URLs signed for an exact length; the API process holds no body; the declared size is checked and reserved before any URL is signed, and the completed object is checked by `HEAD` |
| Quota by one atomic `UPDATE … WHERE used + n <= limit`; `release` with `GREATEST(…, 0)`; a daily reconcile to `SUM(size)` | Kept: reservation at upload creation, release on rejection, expiry or deletion, all in the row's transaction; a daily reconciliation with the inv-11 monitor instead of a silent fix |
| After a downgrade the grace sweep deleted the newest files until the account fit, 30 days later | Kept in spirit with a longer window (FL-D2): 90 days, reminders 30, 7 and 1 day before, then the files over the limit go newest first through the ordinary deletion (7 days hidden, FL-D5) |
| Active content (html, svg, js) opened inline on the bucket's origin; PDFs did not open until the content type was pinned (b9be2af03) | Download links pin the content type; active content is always an attachment, for the owner too |
| No lifecycle rule; nothing aborted incomplete multipart uploads | Bucket rules on both homes: abort incomplete multipart uploads after 24 h, expire `transient/` after 3 days (FL-D7); an upload row past its deadline is aborted and released by a sweep |
| S3 objects deleted before the DB commit (a failed commit left a row without bytes); bulk operations swallowed errors | The row goes first in its transaction, the object after the commit (§8.1); a failed object delete is retried by the sweep from a pending-deletion record, never lost |
| The `u-{id[:8]}` prefix collides between users | v2 keys carry the full owner id; legacy keys are handled through their pointer only (ADR 0006) |
| Duplicate names allowed; any type accepted; MIME sniffed from the first bytes, else the declared type | Kept |
| `send_to_knowledge` copied the bytes into the knowledge base | Not taken: Leo indexes the file in place (cabinet; one index per file) |
| Public share links with password, expiry, folder browsing | Not taken in v2 (FL-D3) |
| A Leo @-mention of a file queried a column that does not exist | A file reference resolves through the files contract only |

---

## 2. Decisions

| ID | Question | Proposal | Trade-off | Step |
|---|---|---|---|---|
| **FL-D1** | The cabinet uploads by a form POST of up to 20 × 2 GB through the API; the architecture (§10, §19) uploads directly to the bucket | **Presigned multipart for every upload.** `POST /v1/me/uploads {purpose, filename, content_type, size_bytes}` → upload id and part URLs; the browser PUTs the parts to the bucket; `POST /v1/me/uploads/{id}/complete` → READY. File Manager's `POST /v1/files` then takes `{upload_ids, folder_id, leo}` and answers the cabinet's `UploadResponse`. The cabinet's upload code changes in the cabinet step | The API never holds a body, any size works, a dropped part is retried alone; costs two more round trips per file and a cabinet change |
| **FL-D2** | What happens to files over the limit (downgrade, lapsed plan) | **Decided with the owner's amendment: nothing is deleted at once and everything stays available; new uploads and copies are refused (413 `storage_limit`). The owner has 90 days to free space or return to a plan that fits, with reminders 30, 7 and 1 day before the end; if the limit is still exceeded after 90 days, the files over the limit are deleted, newest first** (through FL-D5's deletion: hidden for 7 days, then gone) | A lapsed account keeps its files for three months at the cost of storage; deletion is announced three times and is the last resort |
| **FL-D3** | Public share links (the draft's token, password, expiry, folder browsing; DATA_MAPPING S-4) | **Not in v2.** The cabinet has none and no native client uses them; migrated links answer a page saying the link expired, with a sign-in link. Sharing is into a workspace | Draft links in the wild stop working at cutover; avoids a public surface with passwords and tickets |
| **FL-D4** | A copy of a 2 GB file streamed through the API would block a request | **A copy shares the object.** Objects are immutable, so a copy is a new row with the same key; the object is deleted when its last row goes. The copy counts against the quota like the original | Instant copies, no bytes moved; deletion checks for other rows of the key in the same transaction |
| **FL-D5** | Deletion with Undo | **Decided with the owner's amendment: the cabinet's Undo toast delays the DELETE as proposed; on the server a deleted file is kept hidden for 7 days — out of every list, search, Leo and workspace, and out of the quota — and support can restore it; it is deleted for good (row, then object) after 7 days.** No trash screen for the person | A mistaken deletion is recoverable through support for a week; the bucket keeps the bytes 7 days longer |
| **FL-D6** | Whose quota a workspace-owned file uses | **The workspace's:** seats × the plan's per-user `file_manager_gb`, from billing's workspace subscription (billing step 12). Until then workspaces exist only in tests (WS-D7) and workspace uploads are refused | One rule per owner; the personal quota never pays for company files |
| **FL-D7** | The S08 key layout | **ADR 0055:** `u/{user_id}/f/{file_id}` for a person's file, `o/{org_id}/f/{file_id}` for a workspace's, `transient/{purpose}/{upload_id}` for uploads other slices claim and move (recordings, attachments), `platform/…` in the EU bucket; the name is never in the key (`Content-Disposition` carries it); an upload is written to its final key; bucket rules: abort incomplete multipart after 24 h, expire `transient/` after 3 days, set by a script on both buckets | Keys reveal no names; prefix copy and erase per person work for v2 objects; legacy keys stay pointer-only |
| **FL-D8** | Sizes | **2 GB per file and 20 files per request (the cabinet); Leo reads 9 extensions up to 50 MB.** Purposes of other slices carry their own caps in the contract (recording 25 MiB, attachment 10 MiB, workspace upload 25 MiB, app build 500 MiB). Migrated files above 2 GB stay | Matches the screens; the draft's 5 GB is not kept for new uploads |

Settled by documents, no decision needed: flat folders and duplicate names (the cabinet); download links of 15 minutes with the content type pinned (§4.3, b9be2af03); avatars outside the quota (ADR 0045); the indexing pipeline belongs to `knowledge`, which reports `LeoUse.status` through a port files reads (until `knowledge` binds it, a Leo file stays `queued`); meetings' native audio upload stays meetings' own.

---

## 3. Design

### 3.1 Layout

```
backend/src/shosai/features/files/
  contracts/            # Uploads (create, complete, claim), FileReader, IndexStatus port, events
  settings.py           # FilesSettings: caps per purpose, link TTL
  module.py, objectives.py, README.md
  domain/               # names, kinds, Leo-readable, purposes and caps, quota arithmetic,
                        #   key layout, upload states
  application/          # uploads, file manager, folders, Leo use, quota, deletion,
                        #   downloads, workspace transfer, account data
  infrastructure/       # tables and repositories, the storage adapter use, the sniffer
  channels/http/        # /v1/me/uploads*, /v1/files*
  channels/tasks.py     # upload sweep, pending deletions, quota reconciliation
  channels/consumers.py # identity and workspaces events
  channels/agent_tools.py
```

### 3.2 Public surface

| Item | Kind | Used by |
|---|---|---|
| `Uploads.claim(session, upload_id, purpose, owner) -> ClaimedObject` | port: a READY upload of that purpose becomes the caller's object (key, size, content type, sha-256 when computed); a second claim answers the same; an unclaimed upload is aborted after its deadline | meetings (recordings), agent (attachments), support, hubs, workspaces (uploads), releases |
| `FileReader.readable(session, viewer, file_ids)`, `FileReader.open(…)` | port: metadata and a stream of files the viewer may read, through the access policy | knowledge (indexing), agent (read tool), workspaces (knowledge items' names) |
| `IndexStatus` | port bound by knowledge: `LeoUse.status`, `progress`, `chunk_count`, `error` per file | files' list |
| `ShareableResource("file", storage_files)` | declared on `FeatureModule.shareable` | workspaces' access policy |
| Events | `files.file.uploaded`, `files.file.deleted`, `files.leo_use.changed` (ids, sizes, codes) | knowledge (index, drop vectors), workspaces (withdraw a deleted file's items), proactive |

### 3.3 Data (each home)

- `storage_files`: id, `user_id`, `org_id`, `access` (shareable: set together or empty), `folder_id`, `name`, `content_type`, `size_bytes`, `object_key` (the full key; legacy keys verbatim), `sha256`, `starred`, `leo_on`, `created_at`, `modified_at`, `deleted_at` (hidden for 7 days, FL-D5). Company isolation with the access policy (WS-D2); indexes on owner, folder, object key and the purge of hidden rows.
- `file_folders`: id, `user_id`, `name`, `leo`, timestamps; personal.
- `uploads`: id, `user_id`, `org_id`, `purpose`, `object_key`, `multipart_id`, `filename`, `content_type`, `size_bytes`, `state` (`pending`, `ready`, `claimed`, `rejected`, `expired`), `expires_at`, `claimed_by`; personal; the reservation lives with the row.
- `storage_usage`: one row per owner (person or workspace): `used_bytes`, `reserved_bytes`, `over_limit_since` (the start of FL-D2's 90 days) and the reminders sent; checks keep the counters ≥ 0; every change in the transaction of the row it counts.
- `object_deletions`: keys whose last row is gone, deleted from the bucket after the commit and retried by the sweep until done.

### 3.4 Flows

1. **Upload.** Create: check the purpose's cap and the owner's limit (`Entitlements`; 503 when unknown), reserve the declared size, create the multipart upload outside the transaction, commit the row, answer part URLs signed for exact lengths. Complete: complete the multipart, `HEAD` the object (size equal to the declared one, else REJECTED, object deleted, reservation released), sniff the type from the first 4 KB, mark READY. File Manager registers READY uploads as files in one transaction (reservation becomes usage); other slices claim them.
2. **Delete.** In one transaction the row is hidden (`deleted_at`), usage is released, Leo stops using it and its workspace knowledge items are withdrawn through `files.file.deleted`. Support's restore within 7 days brings the row back into the quota (an over-limit result starts FL-D2's 90 days) without re-sharing it. After 7 days the purge removes the row and, if no other row has the key, puts the key in `object_deletions`; the object is deleted after that commit and the sweep retries what failed.
3. **Over the limit.** When usage passes the effective limit (a downgrade, a lapse, a restore), `over_limit_since` is set and uploads are refused; a daily job sends the reminders at 60, 83 and 89 days (30, 7 and 1 day before the end) and at 90 days hides the newest files until usage fits, each through the deletion above; usage back under the limit clears the mark.
4. **Leo use.** A file is used when Leo-readable and its own flag or its folder's is on; a change that would pass `knowledge_base_mb` is refused with 409 `leo_limit`; `files.leo_use.changed` tells knowledge to index or drop.
5. **Share and transfer.** Sharing is workspaces' route over files' `ShareableResource`. Transfer: the file must be shared there by its owner; in one workspace-scoped transaction the row's owner becomes the workspace (`org_id`, `user_id` cleared to the workspace's convention), usage moves from the person to the workspace, the knowledge item becomes an upload through workspaces' port, other workspaces' items are withdrawn, one audit row; the object keeps its key (pointer is the truth).
6. **Account data.** Export: the rows and every object by pointer; erase and transfer by pointer (legacy keys) and by `u/{user_id}/` prefix (v2); workspace-owned files belong to the workspace-data registry.

### 3.5 Monitors and telemetry

- inv-11: daily reconciliation per home compares `storage_usage` with `SUM(size_bytes)` per owner and counts objects whose key no row holds; `shosai_files_quota_drift`, `shosai_files_orphaned_objects`, both `StaysAtMost(0)`.
- Upload outcomes by purpose (`shosai_files_uploads_total{purpose, outcome}`), pending deletions and the age of the oldest.

### 3.6 Not in files

- Indexing, chunks and vectors (knowledge); the knowledge base's connectors (connectors, knowledge).
- Meetings' native audio upload and recordings' processing (meetings, capture).
- Workspace knowledge items, their access and audit (workspaces); files only declares the resource and calls the transfer port.

---

## 4. Steps

| # | Step | Skills | Done when |
|---|---|---|---|
| 1 | **Contracts, domain and ADR 0055.** Skeleton; contracts (§3.2) and events; domain: names, kinds, Leo-readable, purposes and caps, quota arithmetic, key layout, upload states; ADR 0055 (FL-D7) | fastapi, python-doctor, api-design, blob-store | Hypothesis tests: a key never names the home or the file name and always carries the full owner id; a reservation never lets usage pass the limit; Leo-readable matches the cabinet's rule **Done 2026-10-18:** `features/files` with `contracts/` (`Uploads.claim` and `UploadNotClaimableError`, `FileReader`, the `IndexStatus` port with the cabinet's stages, port keys) and `contracts/events.py` (uploaded, deleted, restored, Leo use changed); domain: names, kinds and Leo-readable as the cabinet, active content never inline, purposes and caps, ADR 0055's keys, upload states and parts, the quota with reservations, the 90-day window and the 7-day hiding, Leo use and the knowledge limit; ADR 0055; ARCHITECTURE §8.1 and §13.1, DATA_MAPPING §5.3, §6.2 and S-4, and the cabinet's file manager doc updated; 18 tests with Hypothesis |
| 2 | **Tables.** `storage_files` (shareable, company isolation), `file_folders`, `uploads`, `storage_usage`, `object_deletions` in each home; the `ShareableResource` declaration and its isolation tests | fastapi, python-doctor, data-storage, Docker ×4 | Models match the migrated schema; the isolation gate passes for `file`; usage can never go below zero in the database **Done 2026-10-18:** revision `e7b2c5d9a314` in both homes: `storage_files` (company isolation, sweep read), `file_folders`, `uploads`, `storage_usage` (personal; counters and reminders checked by the database), `object_deletions`, and `files_keys_in_use` answering past RLS; `FILE_RESOURCE` declared, every read through `visible_files`; moved from step 7 because the account data registry requires it with the tables: the handler (rows; objects by pointer only, deleted when no row of any owner names them); 8 new tests |
| 3 | **Uploads.** `POST /v1/me/uploads`, `…/{id}/complete`, `GET …/{id}` (parts done, for resume); the reservation; the sweep of pending uploads past their deadline; `Uploads.claim`; the bucket rules script for both homes (FL-D7) | fastapi, python-doctor, api-design, blob-store, task-scheduling, resilience-failure, Docker ×4 | An upload over its declared size is REJECTED and its reservation released; a replayed part overwrites; an abandoned upload is aborted and released by the sweep; a second claim answers the same object; no request holds a body or a DB session across a storage call **Done 2026-10-18:** `/v1/me/uploads` (create with part links signed for exact lengths, resume, complete with the `HEAD` check, cancel); the reservation as one conditional upsert; `Uploads.claim`; the sweep every 15 minutes (revision `f3a9c1e5b207` lets the sweep role read uploads); `object_deletions` retried; `shosai files bucket-rules` (ADR 0055 now names the command); tests run every storage call through guards that fail inside a transaction; a part retried with the same bytes leaves one object (SeaweedFS keeps the first version of a part re-sent with other bytes, S3 the last; completion passes the newest ETag); 8 new tests |
| 4 | **File Manager.** `/v1/files` list, register from uploads (FL-D1), rename, move, star, delete (hidden for 7 days, then the purge: row, then object through `object_deletions`, FL-D5), copy sharing the object (FL-D4), folders, `GET /v1/files/{id}/download` (pinned type, active content as attachment); support's list of a person's hidden files and their restore (`/v1/admin/users/{user_id}/files*`, admin session) | fastapi, python-doctor, api-design, blob-store, task-scheduling | The cabinet's types pass contract tests; a deleted file is out of every list and the quota at once, restorable by support for 7 days, and gone with its object after that; a copy's object survives the original's deletion and goes with the last row; a failed object delete is retried until done |
| 5 | **Quota.** The effective limit from `Entitlements` (`storage_limit` 413, 503 when unknown); over the limit (FL-D2): uploads refused, everything else available, `over_limit_since`, the reminders 30, 7 and 1 day before the end of 90 days (email and the File Manager's banner), and after 90 days the newest files over the limit deleted through FL-D5; the daily reconciliation and the inv-11 monitors | fastapi, python-doctor, consistency-coordination, task-scheduling | Concurrent uploads never pass the limit; a downgrade refuses new bytes at once and deletes nothing for 90 days; each reminder goes once; on day 90 exactly the newest files over the limit are hidden and usage fits; going back under the limit clears the mark; promtool tests pass |
| 6 | **Leo use.** Flags on files and folders, `knowledge_base_mb` (409 `leo_limit`), `/reindex`, `files.leo_use.changed`, the `IndexStatus` port (`queued` until knowledge binds it) | fastapi, python-doctor | Moving into or out of a Leo folder changes use and emits once; the limit counts only Leo-readable files in use |
| 7 | **Identity's deletion window.** A hidden account's files served to nobody (ADR 0045 point 6), through identity's events; the account data handler itself shipped with step 2 | fastapi, python-doctor | A file of an account in its deletion window is in no list, search, Leo read or workspace; cancelling the deletion brings it back; transfer and erasure are proved by step 2's test |
| 8 | **Workspaces.** Consumers of `workspaces.member.removed`, `.workspace.deleted`; `files.file.deleted` withdraws knowledge items; `POST /v1/files/{id}/transfer` through workspaces' `KnowledgeTransfer` port (workspaces' step 9, which ships it first) with the audit row; workspace quota (FL-D6) after billing step 12 | fastapi, python-doctor, consistency-coordination | A transferred file leaves My files and every other workspace in one transaction with one audit row; a removed member's shared files leave the workspace and stay theirs |
| 9 | **Leo's `files` toolset.** search, read (digest), set "use with Leo" (W), move (W), delete (W, irreversible), with plan, preview and execute | fastapi, python-doctor, agent-architecture | The tool specs pass the model-facing test; a write executes only on the planned targets; a read returns only files the person may read |
| 10 | **Cabinet: File Manager and Knowledge uploads on the API.** Presigned uploads with progress and resume, download, the storage meter, mocks deleted | the four Vercel skills, web-design-guidelines, react-doctor | The screens work on real data in 16 languages; react-doctor 100 |
| 11 | **Contract verification and staging.** Upload, download, copy, delete and transfer on `shosai.tech` in both homes; the bucket rules applied on the owner's buckets | fastapi, python-doctor | A 2 GB upload completes and an abandoned one disappears within a day on staging; on each home's real bucket a part re-sent with other bytes leaves an object assembled from the last version (local SeaweedFS keeps the first, files step 3) |

---

## 5. Documents to update on approval

- STATUS.md: files `planned` (done with the approval).
- ADR 0055 (key layout) written in step 1; ARCHITECTURE §8.1 File row and §13.1: the stale single-bucket wording replaced by ADR 0044's per-home buckets.
- `frontend/docs/file-manager-api.md`: the upload by `/v1/me/uploads` (FL-D1), download, the storage limit; `knowledge-base-api.md` unchanged.
- DATA_MAPPING §5.3 and S-4: share tokens and passwords not carried (FL-D3); §6.2 replaced by ADR 0055.

## 6. Risks

| Risk | Mitigation |
|---|---|
| The managed buckets lack lifecycle rules (none configured today) | Step 3 ships the script; step 11 checks it on staging; the upload sweep aborts what the rules would miss |
| A browser cannot PUT to the bucket (CORS) | The bucket CORS rule ships with the lifecycle script; step 11 checks both homes |
| `knowledge` arrives later, so Leo files stay `queued` | The cabinet step waits for knowledge's index port or shows `queued` as "waiting"; the Leo limit and flags work without it |
| Workspace transfer needs a workspaces port that does not exist yet | Recorded in workspaces' plan: `KnowledgeTransfer` in its public surface and first in its step 9, needing only its step 2's tables; files' steps 1–7 do not depend on it |
