# files

The one path for bytes in Shosai: a person's File Manager (files, flat folders, "Use with Leo"), the presigned uploads every slice that takes bytes goes through, download links, the storage quota, and files shared into or handed over to a workspace.

- Plan: [docs/plan/slices/files.md](../../../../../docs/plan/slices/files.md). Decisions: FL-D1…FL-D8 in the plan; key layout [ADR 0055](../../../../../docs/adr/0055-object-key-layout-and-bucket-rules.md).
- Public surface: `contracts` (`Uploads.claim`, `FileReader`, the `IndexStatus` port knowledge binds, their types and errors) and `contracts.events` (`files.file.uploaded`, `.file.deleted`, `.file.restored`, `files.leo_use.changed`).

## Rules the domain holds

- `domain/names.py` — names trimmed, 1 to 120 characters, no slashes or control characters, duplicates allowed; each broken rule has its API code.
- `domain/kinds.py` — the cabinet's kinds by extension; Leo reads nine extensions up to 50 MiB; active content (HTML, SVG, scripts, XML) never opens inline.
- `domain/purposes.py` — what an upload is for and its cap: File Manager 2 GB (20 per request), recording 25 MiB, Leo and ticket attachments 10 MiB, workspace upload 25 MiB, app build 500 MiB.
- `domain/keys.py` — `u/{user_id}/f/{file_id}`, `o/{org_id}/f/{file_id}`, `transient/{purpose}/{upload_id}`: the full owner id, never the home or the name.
- `domain/uploads.py` — pending → ready (size equal to the declared one) or rejected; ready → claimed; expired after 24 hours; 16 MiB parts within the store's limits.
- `domain/quota.py` — reservations never pass the limit; over the limit nothing goes for 90 days with reminders 30, 7 and 1 day before, then the newest files over it; a deleted file hidden for 7 days.
- `domain/leo.py` — Leo uses a readable file by its own switch or its folder's; the bytes it uses fit `knowledge_base_mb`.

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
- `shosai files bucket-rules [--home ru|eu]` puts ADR 0055's lifecycle and CORS rules on the buckets.
