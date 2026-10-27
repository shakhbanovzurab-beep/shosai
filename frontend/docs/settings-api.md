# Settings API

The contract between the Settings dialog (opened from the user menu) and the preferences that other
slices still own. The TypeScript types in `src/features/settings/domain/*-contract.ts` are the source of
truth; the development mocks in `src/features/settings/mocks/` answer `/api/settings/*` until each owner
publishes its routes. Errors use `{"detail": "message"}`.

**Account and Privacy are identity's** and run on the real API (identity step 11): the profile, avatar and
consents on `GET/PATCH /v1/me` and `PUT/DELETE /v1/me/avatar`; devices on `/v1/me/devices*`; the data
export on `POST /v1/me/exports` and `GET /v1/me/exports/latest`; account deletion on `POST /v1/me/deletion`
(7-day window, a fresh sign-in within 15 minutes, re-verified by an emailed code in the dialog). See the
backend's OpenAPI and `docs/plan/slices/identity.md`. Privacy's "Don't keep my meetings" is notes' setting on
`GET/PUT /v1/notes/settings` (`keep_meetings`, MT-D6), see `notes-api.md`. The per-kind data lists of Privacy (shared chats,
artifacts, uploaded files, feedback) return when their owners serve them.

## Endpoints (prefix `/v1/settings`)

| Method   | Path              | Body                                        | Response               |
| -------- | ----------------- | ------------------------------------------- | ---------------------- |
| `GET`    | ``                | —                                           | `UserSettings`         |
| `PATCH`  | ``                | any subset of `UserSettings`                | `UserSettings`         |
| `GET`    | `/billing`        | —                                           | `Billing`              |
| `GET`    | `/billing/invoices/{id}` | —                                    | the invoice PDF        |
| `POST`   | `/usage/top-up`   | `{"pack_id": str}`                          | `{"url": str}`         |
| `POST`   | `/billing/portal` | `BillingPortalRequest` (intent)             | `{"url": str}`         |
| `GET`    | `/usage`          | — (served: `GET /v1/settings/usage`, billing step 6) | `Usage`       |
| `GET`    | `/mcp`            | —                                           | `McpServersResponse`   |
| `POST`   | `/mcp`            | `McpServerDraft`                            | `201 McpServer`        |
| `PATCH`  | `/mcp/{id}`       | `{"enabled": bool}`                         | `McpServer`            |
| `DELETE` | `/mcp/{id}`       | —                                           | `204`                  |
| `GET`    | `/memories/summary` | —                                         | `MemorySummary`        |
| `POST`   | `/memories/summary` | `{"message": str}` (ask or update)        | `MemorySummary`        |
| `POST`   | `/memories/summary/refresh` | —                                 | `MemorySummary`        |

## Behaviour the UI relies on

- **Everything saves as it changes.** Switches and selects send a one-field `PATCH`; name fields
  send theirs a moment after typing stops. The UI shows the change at once and rolls back if the
  request fails, so return the full saved `UserSettings`.
- **Leo** is agent's and runs on the real API: `GET` and `PATCH /v1/agent/settings` (see `leo-api.md`):
  `leo_model` (`auto` only until studio publishes the plan's models, `422 leo_model_unavailable`),
  `response_language` (a code from `src/lib/language.ts` or `auto`, `422 response_language_invalid`),
  `response_length` (`concise | balanced | detailed`) and the switches `web_search`, `voice_mode` (off also hides
  the microphone), `knowledge_base_search`, `connected_services_search` — anything off is neither offered nor
  used. Everything is on by default. The fields left on `/api/settings` are capture's.
- **Billing / Usage** are read-only. Invoices carry a human-facing `number`, a `description` and a
  `status` of `paid | pending | failed`; `download_url` points at the PDF (null until issued).
  `payment_methods` lists saved cards (exactly one `is_default`). Adding or updating a card never
  happens in our UI: `POST /billing/portal` returns the acquirer's hosted card-binding page (TBank
  adds the card without a charge, CloudPayments holds 1 ₽ and releases it at once) and the browser
  goes there. Turning auto-renewal off is a switch in this section ([ADR 0054](../../docs/adr/0054-billing-plans-payments-trials-and-refunds.md)). The demo answers 501. Usage meters may have `limit: null` for unlimited.
- **Usage is weekly tokens.** `limits` has one entry per tier (`standard`, `frontier`) for the week
  starting `week_start` and resetting at `resets_at`; `limit_tokens` is null on a plan without a limit.
  The section opens with the one usage view, the only place that shows limits: both tiers, the month's
  meeting minutes (`GET /v1/billing/plans`), storage and the files Leo uses (`GET /v1/files/storage`),
  each meter saying when it resets, running low from 80% and what a reached limit stops. Only frontier models (the expensive ones —
  Claude Opus, GPT Astra and similar) can get extra tokens: `frontier.extra_tokens` is the bought
  balance, spent after the weekly frontier allowance and never reset. `POST /usage/top-up` with a
  `packs[].id` returns the provider's checkout URL; the demo answers 501.
- **MCP.** Remote servers only (`streamable_http` or `sse`). `auth_header` is write-only: store it
  encrypted, never return it; report `has_auth` instead. `tools` is the tool count from the last
  successful connection, or `null`.
- **Memory** is the `memory` slice's and runs on the real API (see `memory-api.md`): the switch is `GET` and
  `PATCH /v1/agent/memory/settings` — off stops Leo using and saving memories and deletes nothing — and the
  facts one by one, with their sources, are `/v1/agent/memory`; Settings › Memory opens them from its "What
  Leo remembers" row under the summary.
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
