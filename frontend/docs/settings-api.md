# Settings API

The contract between the Settings dialog (opened from the user menu) and the FastAPI backend. The
TypeScript types in `src/features/settings/domain/*-contract.ts` are the source of truth; Pydantic
models should mirror them (snake_case). The browser calls `/api/settings/*` route handlers (in
`src/features/settings/server/`), which forward to `${BACKEND_API_URL}/v1/settings/*` when
`BACKEND_API_URL` is set and otherwise answer from an in-memory demo in `src/features/settings/server/`.
Errors use `{"detail": "message"}`.

## Endpoints (prefix `/v1/settings`)

| Method   | Path              | Body                                        | Response               |
| -------- | ----------------- | ------------------------------------------- | ---------------------- |
| `GET`    | ``                | —                                           | `UserSettings`         |
| `PATCH`  | ``                | any subset of `UserSettings` except `email` | `UserSettings`         |
| `POST`   | `/account/delete` | `{"confirm_email": str}`                    | `{"deleted": true}`    |
| `PUT`    | `/avatar`         | multipart, image in `file` (≤ 1 MB)         | `UserSettings`         |
| `DELETE` | `/avatar`         | —                                           | `UserSettings`         |
| `GET`    | `/data/export`    | —                                           | archive download       |
| `GET`    | `/data/{kind}`    | —                                           | `DataItemsResponse`    |
| `DELETE` | `/data/{kind}`    | —                                           | `204` (all of the kind)|
| `DELETE` | `/data/{kind}/{id}` | —                                         | `204`                  |
| `GET`    | `/billing`        | —                                           | `Billing`              |
| `GET`    | `/billing/invoices/{id}` | —                                    | the invoice PDF        |
| `POST`   | `/usage/top-up`   | `{"pack_id": str}`                          | `{"url": str}`         |
| `POST`   | `/billing/portal` | `BillingPortalRequest` (intent)             | `{"url": str}`         |
| `GET`    | `/usage`          | —                                           | `Usage`                |
| `GET`    | `/mcp`            | —                                           | `McpServersResponse`   |
| `POST`   | `/mcp`            | `McpServerDraft`                            | `201 McpServer`        |
| `PATCH`  | `/mcp/{id}`       | `{"enabled": bool}`                         | `McpServer`            |
| `DELETE` | `/mcp/{id}`       | —                                           | `204`                  |
| `GET`    | `/memories`       | —                                           | `MemoriesResponse`     |
| `DELETE` | `/memories`       | —                                           | `204` (forget all)     |
| `GET`    | `/memories/summary` | —                                         | `MemorySummary`        |
| `POST`   | `/memories/summary` | `{"message": str}` (ask or update)        | `MemorySummary`        |
| `POST`   | `/memories/summary/refresh` | —                                 | `MemorySummary`        |
| `DELETE` | `/memories/{id}`  | —                                           | `204`                  |

## Behaviour the UI relies on

- **Everything saves as it changes.** Switches and selects send a one-field `PATCH`; name fields
  send theirs a moment after typing stops. The UI shows the change at once and rolls back if the
  request fails, so return the full saved `UserSettings`.
- **Account.** `full_name` must not be empty. `email` is read-only (sign-in is OAuth 2.0 with a
  provider). `display_name` is what Leo calls the user. `work_role` is an id from `WORK_ROLES`
  ("What best describes your work?").
- **Deleting the account** needs the account's email retyped as `confirm_email`; reject a mismatch
  (422) before touching anything. Delete chats, notes, knowledge base, prompts, memory and settings,
  cancel any subscription, then end the session; the UI sends the browser to `/`. The demo checks
  the email and answers 501 without deleting.
- **Avatar.** The browser crops the photo to its centre square, applies EXIF rotation and scales it
  to 256×256 (`AVATAR_SIZE`) as WebP (JPEG where WebP can't be encoded) before uploading, so the
  backend receives small images. Still validate type (`AVATAR_TYPES`) and size, store the file and
  return its URL in `avatar_url`; the demo inlines it as a data URL.
- **Privacy.** `improve_models` defaults to false. `share_location` gates the approximate location
  used for weather and time-aware answers.
- **Leo.** `leo_model` is `"auto"` (Leo picks per task) or the id of a text model from the
  subscription's list (`GET /v1/studio/models`, where models now carry `tier: standard | frontier`);
  reject anything else (422). Frontier models draw on the weekly frontier allowance.
  `response_language` is a code from `src/lib/language.ts` or `"auto"`;
  `response_length` is `concise | balanced | detailed`.
  Advanced switches say what Leo may use — `web_search`, `voice_mode` (off also hides the
  microphone), `knowledge_base_search`, `connected_services_search`; anything off is neither
  offered nor used.
- **Your data (Privacy).** `kind` is `shared_chats | shared_artifacts | uploaded_files | feedback`;
  every item has the same shape (`DataItem`) so one list shows them all. Deleting a shared chat or
  artifact turns its public link off; deleting a file removes it from the chats it was attached to.
  `GET /data/export` downloads everything held about the user as one file (never including secrets
  such as MCP auth headers); the demo exports its in-memory state as JSON.
- **Billing / Usage** are read-only. Invoices carry a human-facing `number`, a `description` and a
  `status` of `paid | pending | failed`; `download_url` points at the PDF (null until issued).
  `payment_methods` lists saved cards (exactly one `is_default`). Adding or updating a card never
  happens in our UI: `POST /billing/portal` returns the payment provider's hosted page (e.g. a Stripe
  customer portal or setup session) and the browser goes there. The demo answers 501. Usage meters may have `limit: null` for unlimited.
- **Usage is weekly tokens.** `limits` has one entry per tier (`standard`, `frontier`) for the week
  starting `week_start` and resetting at `resets_at`. Only frontier models (the expensive ones —
  Claude Opus, GPT Astra and similar) can get extra tokens: `frontier.extra_tokens` is the bought
  balance, spent after the weekly frontier allowance and never reset. `POST /usage/top-up` with a
  `packs[].id` returns the provider's checkout URL; the demo answers 501.
- **MCP.** Remote servers only (`streamable_http` or `sse`). `auth_header` is write-only: store it
  encrypted, never return it; report `has_auth` instead. `tools` is the tool count from the last
  successful connection, or `null`.
- **Memory.** `memory_enabled: false` stops new memories; existing ones stay until deleted.
- **Hotkeys.** `hotkeys` holds only the desktop app's global shortcuts the user changed, e.g.
  `{"prompter": "Mod+Alt+Y", "close_app": null}`; `null` turns a shortcut off and a missing id uses
  its default. Ids and defaults are in `src/features/settings/domain/hotkeys.ts` (`open_app` ⌥⌘Z,
  `toggle_recording` ⌥⌘X, `toggle_overlay` ⌥⌘C, `open_settings` ⌥⌘V, `collapse_overlay` ⌥⌘B,
  `close_app` ⌥⌘Space, `live_translation` ⌥⌘P, `prompter` ⌥⌘T). A combo is `Mod+Alt+Shift+Key` with the
  modifiers in that order (`Mod` is ⌘ on macOS, Ctrl on Windows) and a physical key name from
  `KeyboardEvent.code` without its `Key`/`Digit` prefix (`Z`, `1`, `Space`, `Comma`, `F5`). A PATCH
  replaces the whole map. Reject with `422`: a combo without `Mod` or `Alt`, a system shortcut
  (`Mod+Space`, `Mod+Tab`, `Mod+Q`, `Mod+W`, `Mod+Alt+Escape`), or one already used by another
  command. The desktop app reads the effective shortcuts from `GET /settings`.
- **Memory summary** (like ChatGPT's): a model-written overview of what Leo has learned, as titled
  `sections`, plus `suggestions` for "Learn more". `POST /memories/summary` takes a question about it
  or a correction ("Forget that I…") and returns the updated summary; `refresh` rewrites it from the
  latest memories. The demo can't run a model, so it files messages under a "Notes from you" section.
