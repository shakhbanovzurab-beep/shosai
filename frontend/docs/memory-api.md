# Memory API

What Leo remembers about the person, fact by fact ([ADR 0030](../../docs/adr/0030-leo-memory-v2.md),
[Leo architecture](../../docs/design/leo/ARCHITECTURE.md) §7.2, slice map SM-6), on the routes of the Leo
architecture §13.2. The TypeScript types in `src/features/memory/domain/contract.ts` are the source of truth
(snake_case). The backend's `memory` slice is not built yet: the development mocks in
`src/features/memory/mocks/` answer the same `/v1` paths, so the cabinet needs no change when it ships.
Errors use the backend's envelope (ADR 0008).

| Method   | Path                            | Body                                 | Response       |
| -------- | ------------------------------- | ------------------------------------ | -------------- |
| `GET`    | `/v1/agent/memory?cursor=`      | —                                    | `FactsPage`    |
| `PATCH`  | `/v1/agent/memory/{id}`         | `{"statement"?: str, "pinned"?: bool}` | `MemoryFact` |
| `POST`   | `/v1/agent/memory/{id}/accept`  | —                                    | `MemoryFact`   |
| `DELETE` | `/v1/agent/memory/{id}`         | —                                    | `204`          |
| `DELETE` | `/v1/agent/memory`              | —                                    | `204`          |

`POST /v1/agent/memory` (a fact the person adds) is in the Leo architecture too; the cabinet does not use
it: the person tells Leo what to remember through the summary's "Ask or update" box.

## Behaviour the UI relies on

- **A fact** has a `kind` (`preference`, `fact`, `relationship`, `goal`, `procedure`), a `statement` in the
  person's language (shown as written, `dir="auto"`), a `status` (`candidate` or `active`; forgotten facts are
  never listed), `pinned`, a `source` and `created_at`. The source is `{kind, title}`: `user_statement` (a
  chat), `meeting` (with the meeting's title), `settings` or `user_edit`; every fact shows it.
- **Candidates** ("Should Leo remember this?") are not used in answers until accepted. `accept` makes one
  active; turning one down is `DELETE /{id}`.
- **Editing supersedes.** A new `statement` closes the old fact and opens a new one with `source.kind:
  "user_edit"`: the answer carries a new `id`, which replaces the old row.
- **Forgetting** hides the fact at once and sends `DELETE /{id}` after five seconds unless the person presses
  Undo in the dialog's footer (a toast would be unreachable behind the modal). Forgetting everything is
  confirmed first and cannot be undone.
- **Pages.** `next_cursor` is null on the last page; "Show more" appends the next one. Search and the kind
  filter work on the loaded facts.
- **The off switch** (`memory_enabled` in Settings) stops Leo using and saving facts; the page keeps them and
  says so.
