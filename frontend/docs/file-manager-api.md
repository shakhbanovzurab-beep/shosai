# File Manager API

The contract between File Manager (`/app/file-manager/**`), the parts of the cabinet that use the
account's files (Knowledge, Leo), and the backend's `files` slice ([files plan](../../docs/plan/slices/files.md),
[ADR 0055](../../docs/adr/0055-object-key-layout-and-bucket-rules.md)). The OpenAPI schema is the source of
truth: `src/lib/api/generated/schema.d.ts`, and `src/features/file-manager/domain/contract.ts` names the shapes
the slice uses, held equal to the schema by `contract.test.ts`. The browser calls `/v1/*` through the typed
client; `npm run dev` answers the same routes from the slice's mocks (`src/features/file-manager/mocks/`).
Errors use the platform envelope `{error: {code, params?}}` (ADR 0008).

## One place for files

File Manager is the only place the account's files are stored. Nothing else keeps its own copy:

- **Leo** uses a file when the file, or the folder it is in, is marked "Use with Leo". The file is
  indexed once; `FileItem.leo` carries the index status. The Knowledge screen lists these files
  (see `knowledge-base-api.md`) and uploads through the same path with `leo: true`.
- **Workspaces** point to a file the owner shares there (see `workspace-api.md`). It stays the owner's and
  leaves the workspace when the owner deletes it. The owner can hand it over instead (`POST /v1/files/{id}/transfer`,
  served since files step 8a): it becomes the workspace's, leaves My files and every other workspace, and the same
  people of that workspace keep reading it. The cabinet shows the transfer once the workspace screens are on the API
  (workspaces steps 14a–14b); until then workspaces exist only in tests (WS-D7).

## Endpoints

| Method   | Path                                | Body                                                  | Response                        |
| -------- | ----------------------------------- | ----------------------------------------------------- | ------------------------------- |
| `POST`   | `/v1/me/uploads`                    | `{purpose: "file_manager", filename, content_type, size_bytes}` | `201 UploadOut` (part links) |
| `GET`    | `/v1/me/uploads/{id}`               | —                                                     | `UploadOut` (parts done, fresh links for the rest) |
| `POST`   | `/v1/me/uploads/{id}/complete`      | —                                                     | `UploadOut` (`state: "ready"` or `"rejected"`) |
| `DELETE` | `/v1/me/uploads/{id}`               | —                                                     | `204` (the reservation comes back) |
| `GET`    | `/v1/files`                         | —                                                     | `FilesResponse` (folders, files, newest first) |
| `POST`   | `/v1/files`                         | `{upload_ids (1–20), folder_id?, leo?}`               | `201 UploadResponse`            |
| `PATCH`  | `/v1/files/{id}`                    | `{name?, folder_id?, starred?, leo?}`                 | `FileItem`                      |
| `DELETE` | `/v1/files/{id}`                    | —                                                     | `204`                           |
| `POST`   | `/v1/files/{id}/copy`               | `{name?}`                                             | `201 FileItem`                  |
| `POST`   | `/v1/files/{id}/reindex`            | —                                                     | `FileItem`                      |
| `POST`   | `/v1/files/{id}/transfer`           | `{workspace_id}`                                      | `204`                           |
| `GET`    | `/v1/files/{id}/download`           | —                                                     | `{url, expires_at}`             |
| `GET`    | `/v1/files/storage`                 | —                                                     | `StorageStanding`               |
| `POST`   | `/v1/files/folders`                 | `{name}`                                              | `201 FileFolder`                |
| `PATCH`  | `/v1/files/folders/{id}`            | `{name?, leo?}`                                       | `FileFolder`                    |
| `DELETE` | `/v1/files/folders/{id}`            | —                                                     | `204`                           |

## Behaviour the UI relies on

- **Uploads go straight to the bucket (FL-D1)** through the shared client in `src/lib/uploads/`, which Notes uses for recordings too. Up to 2 GB a file, 20 at a time (`MAX_UPLOAD_BYTES`,
  `MAX_FILES_PER_UPLOAD`). The server signs every part for its exact length; the browser `PUT`s the parts three at a
  time with progress, two files at a time. A part that fails is sent again up to four times with fresh links from
  `GET /v1/me/uploads/{id}`, so a dropped connection or an expired signature costs that part, not the file. An
  upload that fails for good is cancelled at once; a cancellation that does not arrive is the daily sweep's. Ready
  uploads become files in one `POST /v1/files`; a repeat answers the same files. The links carry signed headers; the
  browser sets `Content-Length` and `Host` itself.
- **The upload panel.** File Manager and Knowledge show every upload of the tab as a row: waiting, sent bytes with
  the time left, saving, done. A file refused before it starts (empty, over 2 GB, past 20, a type Leo can't read)
  is a row with its reason, not a toast. Stopping a row aborts its parts and sends `DELETE /v1/me/uploads/{id}`, so
  the reservation comes back at once. Retrying a row whose bytes are already in the bucket only registers it again;
  a registration answering `upload_not_claimable`, `upload_not_found` or `upload_closed` sends the bytes anew. Done
  rows leave after a few seconds; toasts speak only when no panel is on screen.
- **Download (FL-D9).** `url` is a 15-minute link on Shosai's own address (`/dl/{home}/…`) with the file's name and
  pinned type, so a plain `<a download>` saves it; the edge streams the bytes with `nosniff` and a sandbox, and
  active content (HTML, SVG, scripts) always downloads. A file shared with the person downloads too.
- **Storage (FL-D2).** An upload or a copy over `file_manager_gb` answers 413 `storage_limit` with
  `params.limit_bytes` (403 `storage_not_included` when the plan has no storage, 503 `entitlements_unavailable`
  when the plan cannot be read). `GET /v1/files/storage` feeds the storage meter, the Knowledge meter and their
  banners: a null limit is unlimited; `removal_at` and `leo_removal_at` are set only over a limit and are the dates
  the banners name. Over the storage limit after a plan change nothing is removed for 90 days, with reminder emails
  30, 7 and 1 day before; then the newest files over the limit are deleted as below.
- **Leo.** `leo_readable` is true for `LEO_EXTENSIONS` up to 50 MB (`LEO_MAX_FILE_BYTES`); marking another file
  answers 409 `leo_unreadable`. A file's `leo` is null while Leo doesn't use it; otherwise `via` is `file` or
  `folder`, with `status`, `progress`, `chunk_count` and `error` as in the Knowledge API; it stays `queued` until
  knowledge reports indexing. A change that would start Leo using files past `knowledge_base_mb` answers 409
  `leo_limit` with `params.limit_bytes` (0 when the plan includes none). After a plan change leaves Leo over the
  limit, it keeps what it uses for 90 days with reminders, then stops using the newest files over it (FL-D10): a
  readable file in a folder Leo reads with `leo: null` is held, and the menu says so; switching it on within the
  limit brings it back. `/reindex` of a file Leo does not use answers 409 `leo_not_used`.
- **Names** are 1–120 characters without `/` or control characters (`name_required`, `name_too_long`, `name_slash`,
  `name_control_character`). Renaming a file updates `modified_at`. A copy shares the stored bytes, is instant,
  counts against the limit like the original and is named `Report (2).pdf` without `name`.
- **Deleting (FL-D5).** The UI hides a file or folder at once and sends `DELETE` when its Undo toast closes. A
  deleted file is out of every list and the quota at once and is hidden for 7 days, restorable by support. Deleting
  a folder moves its files to My files (`folder_id: null`); files Leo read only through that folder stop being used.
- **Polling.** The UI re-reads `GET /v1/files` every 1.5 s while knowledge works on a file (`parsing`, `chunking`,
  `embedding`), and for 30 s after the set of queued files changes: a queued file waits for knowledge, and an open
  tab does not poll for as long as the queue stands.
- **Errors** the UI words (`domain/problems.ts`): `file_not_found`, `folder_not_found` (409 when moving into a
  folder that is gone), `upload_count`, `upload_not_claimable`, `upload_too_large`, `upload_incomplete`,
  `upload_closed`, `upload_not_found`, `filename_invalid`, the storage, Leo and name codes above.
- **Transfer** needs the file shared in that workspace by the person (409 `share_first`); a workspace that is
  missing or not theirs answers 404 `workspace_not_found`, a suspended one 423 `workspace_suspended`. The file
  keeps the level it was shared at, leaves its folder and the person's Leo, and its bytes leave the person's
  storage; a repeat answers 204 again, and a file already given elsewhere is `file_not_found`.
- **Support (admin session):** `GET /v1/admin/users/{user_id}/files?home=` lists the person's files deleted within
  7 days; `POST /v1/admin/users/{user_id}/files/{file_id}/restore {home}` brings one back, shared nowhere. Neither
  works while the account is in its deletion window (409 `account_deletion_scheduled`); both are audited.

## Development

`npm run dev:api` proxies `/v1` to `BACKEND_URL` and `/dl/{ru,eu}/` to the local bucket (`BUCKET_URL`, default
`http://127.0.0.1:18333`), as the edge does. For downloads to land there, start the API with
`FILES_DOWNLOAD_BASE_URL=http://localhost:<vite port>/dl`; the buckets' CORS must allow that origin for the
browser's part `PUT`s (`shosai files bucket-rules`, see `docs/development.md`).
