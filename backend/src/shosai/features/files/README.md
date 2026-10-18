# files

The one path for bytes in Shosai: a person's File Manager (files, flat folders, "Use with Leo"), the presigned uploads every slice that takes bytes goes through, download links, the storage quota, and files shared into or handed over to a workspace.

- Plan: [docs/plan/slices/files.md](../../../../../docs/plan/slices/files.md). Decisions: FL-D1…FL-D9 in the plan; key layout [ADR 0055](../../../../../docs/adr/0055-object-key-layout-and-bucket-rules.md).
- Public surface: `contracts` (`Uploads.claim`, `FileReader`, the `IndexStatus` port knowledge binds, their types and errors) and `contracts.events` (`files.file.uploaded`, `.file.deleted`, `.file.restored`, `files.leo_use.changed`, `.leo_use.reindex_requested`).

## Rules the domain holds

- `domain/names.py` — names trimmed, 1 to 120 characters, no slashes or control characters, duplicates allowed; each broken rule has its API code.
- `domain/kinds.py` — the cabinet's kinds by extension; Leo reads nine extensions up to 50 MiB; active content (HTML, SVG, scripts, XML) never opens inline.
- `domain/purposes.py` — what an upload is for and its cap: File Manager 2 GB (20 per request), recording 25 MiB, Leo and ticket attachments 10 MiB, workspace upload 25 MiB, app build 500 MiB.
- `domain/keys.py` — `u/{user_id}/f/{file_id}`, `o/{org_id}/f/{file_id}`, `transient/{purpose}/{upload_id}`: the full owner id, never the home or the name.
- `domain/uploads.py` — pending → ready (size equal to the declared one) or rejected; ready → claimed; expired after 24 hours; 16 MiB parts within the store's limits.
- `domain/quota.py` — reservations never pass the limit; over the limit nothing goes for 90 days with reminders 30, 7 and 1 day before, then the newest files over it; a deleted file hidden for 7 days.
- `domain/leo.py` — Leo uses a readable file by its own switch or its folder's; only readable files in use count; a change that starts using files is refused when the bytes in use would pass `knowledge_base_mb`, one that only stops using files never is.

## Tables (each home, revision `e7b2c5d9a314`)

- `storage_files` — the shareable `file` resource (company isolation; personal rows guarded by workspaces' access policy, WS-D2); `object_key` is the full key, legacy keys verbatim, several rows may share one (FL-D4); `deleted_at` hides a file for 7 days (FL-D5). Every read starts from `application/visibility.py`: the policy's predicate plus "not hidden".
- `file_folders`, `uploads`, `storage_usage` (a person's used and reserved bytes, never negative, and the 90-day mark) — personal; a workspace's own quota comes with step 8.
- `object_deletions` — keys whose last row is gone, until the bucket confirms; keys only.
- `files_keys_in_use(keys)` — which keys any row still names, past row-level security, keys only.
- Account data: rows of the person's own files, folders, uploads and usage; objects copied by their keys and deleted only when no row of any owner names them, never by prefix (a file handed to a workspace keeps its key).

## Uploads (step 3)

- `POST /v1/me/uploads {purpose, filename, content_type, size_bytes}` → the part links, each signed 15 minutes for its exact length; `GET /v1/me/uploads/{id}` → parts done and fresh links for the rest; `POST …/{id}/complete` → `ready`, or `rejected` when the object is not the declared size (its object deleted, its bytes released); `DELETE …/{id}` abandons an open upload.
- A File Manager upload reserves its bytes against `file_manager_gb` by one conditional upsert (413 `storage_limit`, 403 `storage_not_included` at 0) and lands on the file's final key; other purposes land under `transient/` and reserve nothing.
- `Uploads.claim(session, upload_id, purpose)` in the uploader's transaction: ready → claimed, a File Manager upload's bytes become used; a repeat answers the same object.
- Every storage call runs outside a transaction; states change by conditional updates. The sweep (`files.sweep_uploads`, every 15 minutes per home) lists due uploads as the sweep role, closes each in its owner's transaction and retries recorded object deletions.
- `shosai files bucket-rules [--home ru|eu]` puts ADR 0055's lifecycle and CORS rules on the buckets; the CORS rule admits the cabinet's origin from `PUBLIC_BASE_URL` and any in `CORS_ALLOWED_ORIGINS` (a development server).

## File Manager (step 4)

- `GET /v1/files` — the person's folders by name and own files newest first; `POST /v1/files {upload_ids, folder_id?}` claims 1–20 ready File Manager uploads in one transaction (the file's id is the upload's, so a repeat answers the same files) and emits `files.file.uploaded`; `PATCH /v1/files/{id} {name?, folder_id?, starred?}` (`folder_id: null` moves to the root); `POST /v1/files/{id}/copy {name?}` — a new row on the same object, `Report (2).pdf` by default, charged against the limit by one conditional upsert; folders `POST/PATCH/DELETE /v1/files/folders*`, a deleted folder's files move to the root.
- `DELETE /v1/files/{id}` hides the file at once (`deleted_at`), frees its bytes and emits `files.file.deleted`. Support (`application/support_files.py`, audited since step 7) lists a person's hidden files and restores one (`/v1/admin/users/{user_id}/files?home=`, `…/{file_id}/restore {home}`, admin session): it returns to the quota, shared nowhere, with `files.file.restored`. `files.purge_hidden` (hourly per home) removes rows hidden for 7 days in their owners' transactions and records the objects no row names for deletion.
- `GET /v1/files/{id}/download` — for any file the person may read: a 15-minute link with the stored type pinned, active content as attachment, rewritten onto `FILES_DOWNLOAD_BASE_URL` (`{base}/{home}{bucket path}?{signature}`). The edge (`deploy/staging/nginx/templates/shosai/downloads.conf.template`) forwards the raw request line to the home's bucket and adds `nosniff` and `sandbox` (FL-D9). Outside development the base is required by the production check `downloads_through_edge`.

## Quota (step 5)

- The limit is `file_manager_gb` from billing's `Entitlements`, read per request: an upload or a copy over it answers 413 `storage_limit`, 403 `storage_not_included` at 0, 503 when the plan cannot be read; concurrent reservations never pass it (one conditional upsert each).
- Over the limit (FL-D2) everything stays available and only new bytes are refused. `application/quota_watch.py` decides one step under the usage row's lock (`domain/quota.py::quota_action`): mark `over_limit_since`, clear it once usage fits, a reminder (`files.storage_over_limit`, account mail, 30, 7 and 1 day before the end, counted and written in one transaction so each goes once), and on day 90 the newest files over the limit through the ordinary deletion (`application/deletion.py`).
- `files.check_quota` (daily per home) lists the people who hold bytes or carry a mark as the sweep role and takes each one's due step; a plan change (`billing.subscription.changed`, consumer `files.quota_follows_plan`) and support's restore mark or clear at once. The reminder's address comes from identity's `AccountProfile.email`.
- `GET /v1/files/storage` answers the meter and the banner: used bytes, the limit, `over_limit_since` and `removal_at`.
- inv-11: `files.reconcile_storage` (daily per home) counts people whose counter differs from the sum of their visible personal files and objects under `u/` and `o/` older than a day that no row names and no deletion waits for; gauges `shosai_files_quota_drift` and `shosai_files_orphaned_objects`, monitors `StorageCounterDrift` and `OrphanedObject` ([runbook](../../../../../docs/runbooks/alerts.md#storage-counter-drift)); nothing is fixed silently. Revision `a7d3e9f1c428` lets the sweep role read `storage_usage`.

## Leo's use (step 6)

- A file is used when Leo can read it (nine types up to 50 MiB) and its own switch or its folder's is on; `FileItem.leo` says `via` and the indexing stage from knowledge's `IndexStatus` port — `queued` until knowledge binds it.
- `PATCH /v1/files/{id} {leo}`, `POST /v1/files {…, leo}` and `PATCH /v1/files/folders/{id} {name?, leo?}` switch it; a move or a rename can start or stop it too; a copy starts without its own switch; deleting a folder stops the use of files Leo read only through it. The file's own switch is refused for a file Leo cannot read (409 `leo_unreadable`).
- `application/leo_use.py` runs every such change the same way: the limit read from `Entitlements` before the transaction when the change may start a use (503 when unread); the person's Leo lock first in the transaction (`infrastructure/leo_lock.py`, a transaction-scoped advisory lock, so a folder switched on while a file moves into it never loses the file); the change flushed; the bytes in use counted (409 `leo_limit` with `limit_bytes` when a started use passes the limit); one `files.leo_use.changed` per file whose use changed, written in one statement (`EventOutbox.add_all`).
- Deleting a file announces `files.file.deleted` only; support's restore brings the use back with `files.leo_use.changed` and is not refused by the knowledge limit, as it is not by the storage limit. A lowered limit refuses new use at once; what Leo already uses stays until FL-D10's 90 days run out (step 6b).
- A person's locks go in one order: the Leo lock, the usage row (`usage_store.lock`), then the files. Day 90's removal holds the row and then every file, so a copy, a deletion, a restore and an erasure take the row before their file.
- `POST /v1/files/{id}/reindex` asks knowledge to read a file again (`files.leo_use.reindex_requested`) and answers it `queued`; 409 `leo_not_used` when Leo does not use it.

## Over the knowledge limit (step 6b, FL-D10)

- Revision `b6e2d8f4a173`: `storage_usage.leo_over_limit_since` and `leo_reminders_sent` (checked like FL-D2's), `storage_files.leo_held`, and the sweep role reads `file_folders`.
- `application/leo_watch.py` takes one step at a time under the person's Leo lock and usage row, with FL-D2's rules from `domain/quota.py` over the bytes Leo uses: mark `leo_over_limit_since`, clear it once the bytes fit, a reminder (`files.leo_over_limit`, account mail in 16 languages, 30, 7 and 1 day before the end) counted and written in one transaction, and on day 90 Leo stops using the newest files over the limit — their own switch off, a file Leo read through its folder held — one `files.leo_use.changed` each. No file is deleted.
- A held file stays out of Leo's use, through its folder too, until the person switches it on (`PATCH {leo: true}`, within the limit); a rename or a folder switch keeps the hold.
- `files.check_leo_limit` (daily per home) lists the people who hold bytes or carry the mark as the sweep role, with the files Leo uses for a whole page in one query, and takes each one's due step; `billing.subscription.changed` (consumer `files.leo_follows_plan`) and support's restore mark or clear at once. A person's own switch-offs clear the mark at the next daily pass, as deletions do for FL-D2.
- `GET /v1/files/storage` adds `leo_used_bytes`, `leo_limit_bytes`, `leo_over_limit_since` and `leo_removal_at` for the Knowledge meter and banner; `shosai_files_leo_quota_actions_total{action}` counts the steps.

## Identity's deletion window (step 7, ADR 0045 point 6)

- Revision `c4f9a1e7d250`: `storage_files.account_hidden`, `storage_usage.account_hidden` and `account_event_at`.
- `identity.account.deletion_scheduled` (consumer `files.hide_with_account`) marks every personal file of the person, hidden ones included; `visible_files` leaves them out, so nobody is served them — not the owner, not a workspace they are shared in (even before workspaces hides the membership), not Leo, not a download, not background work. `.deletion_cancelled` (`files.show_with_account`) shows them again, unchanged.
- `application/account_window.py` locks the usage row first and records the event's time there; an event older than the last one applied changes nothing, so deliveries out of order end where the latest says.
- During the window the daily passes of FL-D2 and FL-D10 leave the person alone: no reminder, no removal, nothing switched off. Erasure and transfer go through the account data handler of step 2, whatever the flags say.
- Support's list and restore of deleted files live in `application/support_files.py` (`HiddenFiles` keeps the purge): an account in its window answers 409 `account_deletion_scheduled` to both, so only cancelling the deletion brings its files back; every list and restore is recorded through identity's `identity.operator_audit` port (`files_listed`, `file_restored` with the file's id) and reaches the admin's EU audit log.

## Workspaces (step 8a)

- `POST /v1/files/{id}/transfer {workspace_id}` (`application/file_transfer.py`) hands a file the person shared in a workspace over to it, in one transaction scoped to that workspace with the person's locks in their order (Leo lock, usage row, file): workspaces' `KnowledgeTransfer` turns the shared item into the workspace's upload, withdraws the file from every other workspace and writes the audit row; the row then takes `org_id` and the item's level, leaves its folder and the person's Leo, and its bytes leave the person's usage (the workspace's own usage is step 8b, FL-D6). The object keeps its key. A repeat answers 204; a file given elsewhere is `file_not_found`.
- `workspaces.member.removed` (consumer `files.follow_departure`) passes the departed member's workspace files to the owner the event names (nfr-16); their personal files stay theirs.
- `workspaces.workspace.deleted` (`files.erase_with_workspace`) erases the workspace's files and uploads, one `files.file.deleted` each for knowledge, and records only the keys no other row names; the upload sweep deletes those objects.
- A deleted personal file leaves every workspace it was shared in through workspaces' consumer `workspaces.withdraw_deleted_file`.

## `FileReader` and Leo's `files` toolset (step 9)

- `application/file_reader.py` binds `files.file_reader`: `facts(session, viewer, ids)` in the caller's transaction and `open(home, viewer, id)` after a short access check of its own, both starting from `visible_files`, so a deleted file and a file of an account in its deletion window are read by nobody. Knowledge indexes files and re-checks every search hit through it; the agent's read tool below uses it.
- `channels/agent_tools.py` declares the toolset (Leo §8.1), `channels/agent_tool_reads.py` and `channels/agent_tool_writes.py` bind it:
  - `files.search` — files the person may read whose name contains the query (any language; `%` and `_` are literal), newest first, at most 20, with `owned` and, for own files, the folder and Leo's use;
  - `files.read` — a file's facts through `FileReader` and, for txt, md, csv and json, its first 16 KiB as an excerpt of at most 6,000 characters; other kinds answer `no_excerpt: not_text` until knowledge parses them;
  - `files.set_leo_use` (a file or a folder), `files.move`, `files.delete` — `plan` checks the target is the person's own and freezes it, `preview` is `agent.files.set_leo_use|move|delete` with the names, `execute` applies the plan in the person's transaction through the same edits as the routes (`application/file_edits.py`, `Folders.change`), once per item key with `agent.action_item.executed` (core's `ActionItems`). Refusals become typed tool errors: `not_found`, `limit_reached` (the knowledge limit), `unavailable`, `failed` with the slice's code.

