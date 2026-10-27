# Memory API

What Leo remembers about the person, fact by fact ([ADR 0071](../../docs/adr/0071-leo-memory-slice.md),
[Leo architecture](../../docs/design/leo/ARCHITECTURE.md) §7.2, slice map SM-6), on the backend's `memory` slice
([plan](../../docs/plan/slices/memory.md) §3.3). The types come from the backend's OpenAPI
(`src/lib/api/generated/schema.d.ts`), named in `src/features/memory/domain/contract.ts`; the calls are in
`src/features/memory/api/memory-api.ts`. Errors use the backend's envelope (ADR 0008).

| Method   | Path                                     | Body                                     | Response         |
| -------- | ---------------------------------------- | ---------------------------------------- | ---------------- |
| `GET`    | `/v1/agent/memory?kind=&q=&cursor=`      | —                                        | `FactsPageOut`   |
| `PATCH`  | `/v1/agent/memory/{id}` + `Idempotency-Key` | `{"statement"?: str, "pinned"?: bool}` | `MemoryFactOut`  |
| `POST`   | `/v1/agent/memory/{id}/accept`           | —                                        | `MemoryFactOut`  |
| `POST`   | `/v1/agent/memory/{id}/restore`          | —                                        | `MemoryFactOut`  |
| `DELETE` | `/v1/agent/memory/{id}`                  | —                                        | `204`            |
| `DELETE` | `/v1/agent/memory`                       | —                                        | `204`            |
| `GET`    | `/v1/agent/memory/settings`              | —                                        | `{enabled}`      |
| `PATCH`  | `/v1/agent/memory/settings`              | `{"enabled": bool}`                      | `{enabled}`      |
| `GET`    | `/v1/agent/memory/summary`               | —                                        | `MemorySummaryOut` |
| `POST`   | `/v1/agent/memory/summary/refresh`       | —                                        | `MemorySummaryOut` |
| `POST`   | `/v1/agent/memory/summary/messages` + `Idempotency-Key` | `{"message": str}`        | `MemoryMessageOut` |

The list also filters by `status`, `source=imported` (the draft's carried-over candidates, listed only there)
and `thread_id` (a conversation's waiting candidates).

## Behaviour the UI relies on

- **A fact** has a `kind` (`preference`, `fact`, `relationship`, `goal`, `procedure`), a `statement` in the
  person's language (shown as written, `dir="auto"`), a `status` (`candidate` or `active`), `pinned`, a
  `source` and `created_at`. The source is `{kind, title, thread_id, message_id}`: `user_statement` (a chat
  with Leo), `meeting` (with the meeting's title as the person may read it now), `team_chat`, `settings`,
  `user_edit` or `imported`; every fact shows it.
- **Candidates** ("Should Leo remember this?") are not used in answers until accepted. `accept` makes one
  active; turning one down is `DELETE /{id}`.
- **Editing supersedes.** A new `statement` closes the old fact and opens a new one with `source.kind:
  "user_edit"`: the answer carries a new `id`, which replaces the old row. Every `PATCH` sends a fresh
  `Idempotency-Key`, so a retry answers the first result instead of failing on the closed fact.
- **Forgetting** is sent at once; for five seconds the dialog's footer offers Undo, which calls `restore` (the
  server brings a forgotten fact back for a day). A toast would be unreachable behind the modal. Forgetting
  everything is confirmed first and cannot be undone.
- **Pages and filters.** Candidates come first, then facts, newest first; `next_cursor` is null on the last
  page and "Show more" appends the next one. The kind and the words (`q`, sent when the person stops typing)
  are filtered by the server, so they cover the whole memory. `counts` (`active`, `candidates`, `imported`)
  are the whole memory's, for the settings row and the dialog's footer.
- **The off switch** (`/v1/agent/memory/settings`) stops Leo using and saving facts; the page keeps them and
  says so.
- **Leo's changes.** When Leo forgets a fact the person approved on a card, the card names the `memory`
  domain and a shown list reads again.

## The summary and its box (MM-D3)

- **The summary** is `{sections [{title, body}], suggestions [≤ 3], updated_at, stale}`, written by a model from
  the current facts in the interface language. Reading it never calls a model; `sections` is empty when Leo
  remembers nothing, and the dialog says so. `stale` means the facts changed since it was written and a rewrite
  is on its way; the dialog says the latest changes will appear shortly. `refresh` rewrites it now (ten times an
  hour; `409 memory_off`, `403 consent_required`, `503 memory_unavailable`).
- **"Ask or update"** posts `{message}` with a fresh `Idempotency-Key` per message. The answer is
  `{answer, changes, summary}`: `answer` is the answer to a question or null; each change is
  `{change: remembered | updated | forgotten, fact, replaced_id}`. The dialog shows the answer and the changes
  above the box, each with Undo: a remembered fact is forgotten (`DELETE /{id}`), a corrected one is undone by
  restoring `replaced_id`, a forgotten one by restoring it — for a day. After a message the dialog reads the
  summary again while it is stale, for two minutes at most. `409 memory_off`, `403 consent_required`, `429`,
  `503 memory_unavailable` come back as a toast.
