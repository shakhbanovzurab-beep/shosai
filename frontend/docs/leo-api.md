# Leo API

How the cabinet talks to Leo: conversations per context, a turn streamed over SSE with resume, the approval cards
and "Needs you", the answer's sources, Settings › Leo and the rating of answers. The backend's `agent` slice serves
it ([plan](../../docs/plan/slices/agent.md) §3.3, [ADR 0068](../../docs/adr/0068-leo-agent-slice.md); Leo
architecture §13). Shapes are snake_case; errors use the platform's envelope (ADR 0008) with the codes below; pages
are `{items, next_cursor}` with `limit` 1–100 (default 50). The generated client in `src/lib/api/generated/` is the
source of truth once the routes ship; until a step moves a screen to the API, its mocks answer as this document says.

## Conversations

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| `GET` | `/v1/agent/threads?scope=personal\|workspace&workspace_id=&cursor=&limit=` | — | `{items: Thread[], next_cursor}`, newest activity first |
| `POST` | `/v1/agent/threads` with `Idempotency-Key` | `{scope: {kind, workspace_id?}}` | `201 Thread` |
| `GET` / `PATCH` / `DELETE` | `/v1/agent/threads/{id}` | `PATCH {title}` (1–120) | `Thread` / `Thread` / `204` |
| `GET` | `/v1/agent/threads/{id}/messages?cursor=&limit=` | — | `{items: Message[], next_cursor}`, newest first |

```text
Thread  = {id, scope: {kind: personal | workspace | hub, workspace_id | null, hub_id | null}, title | null,
           last_activity_at, created_at}
Message = {id, role: user | assistant | server, text, status: done | stopped | failed | null,
           attachments: [{id, name, size, type}], steps: [{id, activity, detail, status, duration_ms}],
           sources: LeoSource[], artifacts: LeoArtifact[], actions: LeoProposal[],
           feedback: {rating: useful | not_useful, shared} | null, created_at, duration_ms}
```

- The panel opens its context's latest thread; "New chat" empties the panel, and the thread is created when its first
  question is sent (a retry with the same key answers the same thread). Its `title` is null until that question
  names it; the cabinet words an untitled thread itself. The "Recent chats" menu lists the context's threads and
  renames or deletes them. Nothing of a thread is kept in the browser's storage.
- A message carries what exists when its step ships: now `id`, `role`, `text`, `status` (null for a question or a
  server note), `created_at` and `duration_ms`; `steps` and `sources` come with answers over tools, `artifacts` and
  `actions` with the cards, `feedback` with the rating and `attachments` with uploads.
- `POST` with a workspace the person is not in is `404 workspace_not_found`; a workspace scope without
  `workspace_id`, or Personal with one, is `422 scope_invalid`.
- A workspace's threads disappear the moment the person's membership ends (`404 thread_not_found`); they are erased
  7 days later unless the membership comes back. `scope=hub` answers `422 scope_unavailable` until hubs ship.
- A failed or stopped answer keeps the text written so far; the failure itself is never part of the text.

## A turn

`POST /v1/agent/threads/{id}/turns` with `Idempotency-Key: <the client's message id>` and `Accept: text/event-stream`:

```text
{text (1–4 000), upload_ids (≤ 5, presigned uploads of purpose leo_attachment),
 surface: {path ≤ 200, subject?: {kind: meeting | task | board | file, id}}, locale,
 regenerate_of?: <the last question's id>, edit_of?: <the last question's id>, supersede?: bool}
```

- The body grows with the steps that use it: now `text`, `locale` and `supersede`; `surface`, `regenerate_of` and
  `edit_of` come with the context builder, `upload_ids` with attachments. Until then any other field is `422`.
- `regenerate_of` answers the last question again; `edit_of` replaces its text and its answer. Any other id is
  `409 not_last_question`.
- A busy thread answers `409 thread_busy`; `supersede: true` stops the running answer first.
- The same `Idempotency-Key` again streams the same run from its first event.
- Refusals before the stream: `402 token_limit` (`params.limit`: `frontier_weekly_tokens`, `standard_daily_tokens`,
  `standard_weekly_tokens`), `403 consent_required`, `404 thread_not_found`, `409 thread_busy`, `422`,
  `429 rate_limited | too_many_runs | agent_busy` with `Retry-After`, `503 agent_unavailable | entitlements_unavailable`.
- Resume: `GET /v1/agent/runs/{id}/events` with `Last-Event-ID`; `410 run_events_gone` after an hour — reload the
  thread. Stop: `POST /v1/agent/runs/{id}/cancel` (202; asking again, or after the end, changes nothing). Another
  person's run is `404 run_not_found`.
- A run whose worker was lost ends `run.failed {process_lost}` within a minute; the question stays in the thread, so
  "Retry" asks it again.

### Stream events

Every event has a monotonic `id`; a comment line every 15 s keeps the connection open. Unknown event types are
ignored. Exactly one of `run.completed` and `run.failed` ends a run.

| Event | Data |
| --- | --- |
| `run.started` | `{run_id, thread_id, message_id, reply_id}` |
| `step.started` / `step.completed` / `step.failed` | `{id, seq, activity, detail?, duration_ms?, code?}` — `activity` is a tool's name (`notes.search`) or `think`, `write_answer`; an unknown one reads as a generic line |
| `text.delta` | `{text}` |
| `sources` | `{sources: LeoSource[]}` — the whole list so far; its numbers never change within a run |
| `artifact` | `LeoArtifact` |
| `client.action` | `{navigate: {to}}` — a cabinet path, followed only if the cabinet knows the route |
| `action.proposed` / `action.updated` | `{action: LeoProposal}`; `updated` also `{invalidates: string[]}` (query domains to refetch) |
| `run.paused` | `{action_id}` |
| `run.completed` | `{message_id, outcome: answered \| stopped, truncated}` |
| `run.failed` | `{code: model_unavailable \| token_limit \| turn_deadline \| process_lost \| failed}` |

## Sources

```text
LeoSource = {id, kind: meeting | file | task | note | mail | web, title, space, locator | null, quote, highlight: string[]}
```

The answer cites `[n]`, the n-th source counting from one. Sources come from the tools Leo used, never from the
model; `space` is "Personal" in the person's language or the workspace's name. `highlight` stays empty for now —
the quote is shown whole. A marker for a number the list does not have is not drawn.

## Artifacts

```text
LeoArtifact = {kind: "chat_digest", ref, alt, workspace_id, chat_id}
```

The stream carries the reference only; the chats slice serves the digest (`GET /v1/workspaces/{id}/chats/{chat_id}/digests/{ref}`).

## Approval cards and "Needs you"

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| `GET` | `/v1/agent/actions?status=proposed&cursor=&limit=` | — | `{items: LeoProposal[], next_cursor}`, newest first |
| `GET` | `/v1/agent/actions/{id}` | — | `LeoProposal` |
| `POST` | `/v1/agent/actions/{id}/approve` | `{nonce}` | `LeoProposal` (+ `run_id` when the answer goes on) |
| `POST` | `/v1/agent/actions/{id}/reject` | `{nonce}` | `LeoProposal` |

```text
LeoProposal = {id, tool, title, space, origin: {kind: thread | errand | mcp, app}, reversibility, warning, taint,
               preview: {kind: "fields", fields: [{label, value}], body | null}, status, outcome, nonce,
               created_at, expires_at, resolved_at}
status = proposed | executing | succeeded | partially_succeeded | failed | rejected | expired | outcome_unknown
```

- The title, the labels and the values arrive in the person's language: the slice that owns the tool words them.
- A decision on an action that no longer waits is `409 action_not_pending`; the card then shows its final state.
- `approve` waits up to 20 s for the outcome; a slower one answers `executing` and `action.updated` follows on the run's
  stream. When `run_id` comes back, the cabinet follows that run's events for Leo's closing words.
- `warning: true` asks for a careful decision on the screen; `taint` names what the action was prepared from.
- `outcome_unknown` asks the person to check before retrying: the change may have happened.
- Text-edit previews (`kind: "diff"` with `accepted_changes`) come with the first tool that edits text; until then
  `accepted_changes` is refused (`422`).

## Settings › Leo

`GET /v1/agent/settings`, `PATCH /v1/agent/settings` with any subset; both answer the whole:

```text
{leo_model: "auto", response_language: "auto" | <code>, response_length: concise | balanced | detailed,
 web_search, voice_mode, knowledge_base_search, connected_services_search}
```

Everything is on by default. `leo_model` takes `auto` only until studio publishes its models (`422
leo_model_unavailable`); a language outside the 16 is `422 response_language_invalid`. Anything switched off is
neither offered to Leo nor used; `voice_mode` off also hides the microphone.

## Rating an answer

`PUT /v1/agent/messages/{id}/feedback {rating: useful | not_useful}` → `{rating, shared}`; `DELETE` → `204`.

One press under an answer, the same press again takes it back. The rating counts only in anonymous totals.
`shared` is true when the person's "Help improve the models" consent (Settings › Privacy) let the conversation become
an evaluation case — never for an answer built on a workspace's data.
