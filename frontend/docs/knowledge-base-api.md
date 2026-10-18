# Knowledge API

The contract between the Knowledge screen (`/app/knowledge-base`: what Leo answers from in
Personal) and the FastAPI service that indexes files for Leo and syncs external sources. The
TypeScript types in `src/features/knowledge-base/domain/contract.ts` are the source of truth;
Pydantic models should mirror them field for field (snake_case).

**Files live in File Manager**, not here (see `file-manager-api.md`). Leo uses a file when the file
or its folder is marked "Use with Leo"; the index status is on the file (`FileItem.leo`). There is
one index per file: a workspace the file is shared in answers from the same vectors, filtered by
who may use it there (see `workspace-api.md`). The Knowledge screen is a view over File Manager:
the files Leo uses, the folders it reads, the sources it syncs, and what the account's workspaces
let Leo use for it (`GET /me/knowledge`).

## Wiring

The browser only calls Next.js route handlers under `/api/knowledge-base/*`. Each handler forwards
the request unchanged to the FastAPI service when `BACKEND_API_URL` is set (shared with the
Studio API, see `docs/studio-api.md`):

| Variable                 | Example             | Purpose                                          |
| ------------------------ | ------------------- | ------------------------------------------------ |
| `BACKEND_API_URL`        | `http://api:8000`   | Base URL; requests go to `/v1/knowledge-base/…`  |
| `BACKEND_API_KEY`        | —                   | Optional, sent as `Authorization: Bearer <key>` |

Without `BACKEND_API_URL` the handlers answer from an in-memory demo
(`src/features/knowledge-base/server/demo-*.ts`, next to the route handlers) that simulates the
pipeline and resets on restart.

Errors use FastAPI's shape: `{"detail": "message"}`, or the standard list of validation errors on
422. The UI shows `detail` to the user.

## Endpoints (prefix `/v1/knowledge-base`)

| Method   | Path                      | Body                                  | Response                              |
| -------- | ------------------------- | ------------------------------------- | ------------------------------------- |
| `GET`    | `/index`                  | —                                     | `IndexResponse` (settings, plan limit) |
| `GET`    | `/connectors`             | —                                     | `ConnectorsResponse` (all 12 sources) |
| `PUT`    | `/connectors/{id}`        | `{"config": {field: string}}`         | `ConnectResponse`                     |
| `DELETE` | `/connectors/{id}`        | —                                     | `204`                                 |
| `POST`   | `/connectors/{id}/sync`   | —                                     | `Connector`                           |

Adding a file for Leo is an upload registered by `POST /v1/files` with `leo: true` (File Manager);
stopping is `PATCH /v1/files/{id}` with `{"leo": false}`, or `PATCH /v1/files/folders/{id}` for a folder;
re-reading one is `POST /v1/files/{id}/reindex`.

## Embeddings

Google **Gemini Embedding 2** (`gemini-embedding-2`): 3072-dimensional vectors by default (128–3072 supported; Google recommends 768, 1536 or
3072), up to 8,192 input tokens. Report the model and dimensions in `index` so the
UI shows what is actually in use. The model is multimodal (text, images, PDF, audio, video), so
images can be added to `LEO_EXTENSIONS` (File Manager's contract) once the pipeline handles them.

## Behaviour the UI relies on

- **Indexing runs in the background.** A file Leo starts using is `queued`; its `leo.status` moves
  `queued → parsing → chunking → embedding → indexed`, or to `failed` with a human-readable `error`.
  `progress` is 0–100 within the current step; `chunk_count` is set once chunking is done. The UI
  polls `GET /v1/files` every 1.5 s while a file is being indexed, and for 30 s after the queue changes.
- **What Leo can read.** `LEO_EXTENSIONS`, up to 50 MB each (`LEO_MAX_FILE_BYTES`); `leo_readable`
  says so per file. Enforce it server-side; the UI checks too, but only as a convenience.
- **The plan's limit** (`knowledge_base_mb`) counts the bytes of the files Leo uses, not storage.
  `IndexResponse.limit_bytes` reports it for the effective plan (see `upgrade-api.md`); a change that
  would go over it answers `409`.
- **Stopping, deleting.** Stopping removes the file's vectors from the account's index unless a
  workspace still uses it; deleting the file in File Manager removes them everywhere and withdraws
  the file from every workspace it was shared in.
- **Connectors.** `GET /connectors` returns every source, including disconnected ones. The fields
  each source needs are listed in `src/features/knowledge-base/domain/connectors.ts`.
  - Every source except Website signs in with **OAuth 2.0** at its provider (Atlassian for
    Confluence and Jira, GitHub for Obsidian vaults, Microsoft for SharePoint & OneDrive, Yandex ID
    for Yandex Disk). The UI never asks for passwords or tokens; `config` only carries optional
    scoping (channels, spaces, folders, repositories…).
  - `PUT /connectors/{id}` saves that scoping, sets `status: "connecting"` and returns the
    provider's `authorize_url`. The browser is redirected there; the backend's callback stores the
    tokens, starts the first sync and redirects to `/app/knowledge-base?tab=sources`.
    Website returns `authorize_url: null` and starts crawling straight away.
  - While `status` is `connecting` or `syncing`, the UI polls `GET /connectors` every 1.5 s.
  - Disconnecting deletes the stored credentials and the vectors indexed from that source.
