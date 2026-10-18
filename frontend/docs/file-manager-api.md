# File Manager API

The contract between File Manager (`/app/file-manager/**`), the parts of the app that use the
account's files (Knowledge, workspaces, Leo), and the FastAPI backend. The TypeScript types in
`src/features/file-manager/domain/contract.ts` are the source of truth (snake_case). The browser
calls `/api/files/*`, which forwards to `${BACKEND_API_URL}/v1/files/*` when set and otherwise
answers from an in-memory demo (`src/features/file-manager/server/`). Errors: `{"detail": "message"}`.

## One place for files

File Manager is the only place the account's files are stored. Nothing else keeps its own copy:

- **Leo** uses a file when the file, or the folder it is in, is marked "Use with Leo". The file is
  indexed once; `FileItem.leo` carries the index status. The Knowledge screen lists these files
  (see `knowledge-base-api.md`).
- **Workspaces** point to a file the owner shares there (`POST /workspaces/{ws}/knowledge/publish`,
  see `workspace-api.md`). It stays the owner's, answers from the same index, and leaves the
  workspace when the owner deletes it, stops sharing it, or leaves. The owner can **transfer** it
  instead: it then belongs to the workspace and leaves My files.

## Endpoints

| Method   | Path                      | Body                                                  | Response              |
| -------- | ------------------------- | ----------------------------------------------------- | --------------------- |
| `GET`    | `/files`                  | —                                                     | `FilesResponse` (folders, files, newest first) |
| `POST`   | `/files`                  | multipart: `files` (1–20), `folder_id`?, `leo` = `"true"`? | `201 UploadResponse` |
| `PATCH`  | `/files/{id}`             | `{name?, folder_id?, starred?, leo?}`                 | `FileItem`            |
| `DELETE` | `/files/{id}`             | —                                                     | `204`                 |
| `POST`   | `/files/{id}/copy`        | —                                                     | `201 FileItem`        |
| `POST`   | `/files/{id}/reindex`     | —                                                     | `FileItem`            |
| `POST`   | `/files/{id}/transfer`    | `{workspace_id}`                                      | `204`                 |
| `POST`   | `/files/folders`          | `{name}`                                              | `201 FileFolder`      |
| `PATCH`  | `/files/folders/{id}`     | `{name?, leo?}`                                       | `FileFolder`          |
| `DELETE` | `/files/folders/{id}`     | —                                                     | `204`                 |

## Behaviour the UI relies on

- **Uploads** are up to 2 GB each, 20 at a time (`MAX_UPLOAD_BYTES`, `MAX_FILES_PER_UPLOAD`; `413`
  and `422` otherwise). Uploading into a folder Leo reads, or with `leo=true`, starts indexing.
- **Leo.** `leo_readable` is true for `LEO_EXTENSIONS` up to 50 MB (`LEO_MAX_FILE_BYTES`); other
  files can't be marked. A file's `leo` is null while Leo doesn't use it; otherwise `via` is `file`
  (marked itself) or `folder` (its folder is marked), with `status`, `progress`, `chunk_count` and
  `error` as in the Knowledge API. Moving a file into or out of a folder Leo reads starts or stops
  indexing it. A copy starts unmarked. `POST /reindex` reads the file again (`409` if Leo doesn't
  use it).
- **Limit.** Turning Leo on for a file or folder, uploading with `leo`, or moving into a Leo folder
  answers `409` when the bytes of all files Leo uses would go over the plan's `knowledge_base_mb`.
- **Names** are 1–120 characters without `/` or `\`. Renaming a file updates `modified_at`.
- **Deleting** a file is final. The UI hides it at once and sends `DELETE` when its Undo toast
  closes. It also leaves every workspace it was shared in. Deleting a folder moves its files to My
  files (`folder_id: null`); files Leo read only through that folder stop being used.
- **Transfer** needs the file to be shared in that workspace by the account (`409` otherwise). The
  workspace's knowledge item becomes the workspace's own upload; the file leaves My files and every
  other workspace it was shared in. It can't be undone.
- **Polling.** The UI re-reads `GET /files` every 1.5 s while any file Leo uses is being indexed.

## Backend contract (files plan, approved 2026-10-18)

The backend serves `/v1/files/*` with these changes to the demo above ([files plan](../../docs/plan/slices/files.md), [ADR 0055](../../docs/adr/0055-object-key-layout-and-bucket-rules.md)); the cabinet moves to them in the plan's step 10:

- **Uploads go straight to the bucket (FL-D1).** `POST /v1/me/uploads {purpose: "file_manager", filename, content_type, size_bytes}` answers an upload id and presigned part URLs signed for exact lengths; the browser `PUT`s each part and sends `POST /v1/me/uploads/{id}/complete`. `POST /v1/files {upload_ids, folder_id?, leo?}` then turns ready uploads into files and answers `201 UploadResponse`.
- **Download:** `GET /v1/files/{id}/download` → a 15-minute link with the file's name and type; active content (HTML, SVG, scripts) always downloads.
- **Storage limit (FL-D2):** an upload or a copy over `file_manager_gb` answers 413 `storage_limit`. Over the limit after a plan change nothing is removed for 90 days (reminders 30, 7 and 1 day before); then the newest files over the limit are deleted.
- **Deletion (FL-D5):** the Undo toast stays as it is; a deleted file is hidden for 7 days, out of the quota, and support can restore it.
- **Copy** shares the stored bytes and is instant; it counts against the limit like the original.
