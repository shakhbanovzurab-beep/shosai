# Leo API

How the cabinet talks to Leo: conversations per context, a turn streamed over SSE with resume, the approval cards
and "Needs you", the answer's sources, Settings › Leo and the rating of answers. The backend's `agent` slice serves
it ([plan](../../docs/plan/slices/agent.md) §3.3, [ADR 0068](../../docs/adr/0068-leo-agent-slice.md); Leo
architecture §13). Shapes are snake_case; errors use the platform's envelope (ADR 0008) with the codes below; pages
are `{items, next_cursor}` with `limit` 1–100 (default 50). The generated client in `src/lib/api/generated/` is the
source of truth once the routes ship; until a step moves a screen to the API, its mocks answer as this document says.

The panel talks to the API in Personal and in a workspace (agent steps 7a and 7b): the context's latest thread, the
"Recent chats" menu (open, rename, delete), history by cursor, turns over SSE with resume after `Last-Event-ID`,
"Stop", "Regenerate" and "Edit", steps and sources. Every turn names the page and its subject: a note or a meeting,
a task (`?task=`) or a board (`?board=`); only a UUID is ever sent as a subject's id. Nothing of a conversation is
kept in the browser; old `leo-chat*` keys are erased. A hub and the admin panel keep the
sample `/api/leo` (NDJSON) until agent steps 20 and 16. Since step 12b a question carries attachments. Since step 10 cards and
"Needs you" are on the API too, and `/v1/agent/actions*` has no mocks.

Since agent step 9a1 Leo proposes writes: a write call becomes a card (`action.proposed`) and the run pauses
(`run.paused`); `approve` and `reject` are served, and the card's end follows as `action.updated` on the same run's
stream. Since step 9b1 a card is the whole `LeoProposal` in the person's language (their profile's): `{id, tool,
title, space, origin {kind, app}, reversibility, warning, taint, preview {kind: "fields", fields [{label, value}],
body}, status, outcome, nonce, created_at, expires_at, resolved_at}` — the title and the fields are the slice's
words, `space` is Personal or the workspace's name — the same in the stream, in the decision's answer (which adds
`run_id`), in the inbox and in the history, where an answer and a server note carry their cards in `actions`.
`GET /v1/agent/actions?status=&cursor=&limit=` lists the person's cards newest first ("Needs you" reads
`status=proposed`: only cards still within their hour) and `GET /v1/agent/actions/{id}` reads one. A decided card
adds a server note to the thread (`role: server`, empty `text`) that the cabinet renders from its card; Leo's next
turns read it in plain words. Since step 9a2 an approved card's run resumes: after the two `action.updated`
(`executing`, then the end with `invalidates`) the same run's stream carries the epilogue — `text.delta`, steps,
`sources` — and `run.completed`, and the answer, epilogue included, follows the note in the history. A rejected or
expired card, or a run a new turn closed, gets no epilogue: `action.updated` and, for a run still paused,
`run.completed`.

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
  server note), `created_at`, `duration_ms`, `steps` (an answer's tool calls; empty otherwise, `status` `done`
  or `failed`), `sources` (an answer's, as the `sources` event left them), `artifacts` (what the tools handed over,
  by reference — a team chat's digest) and `actions` (the cards an answer proposed, or the card a server note tells
  about, as they stand), `feedback` (the person's rating of an answer, or null) and `attachments` (a question's
  files: `{id, name, size, type}`; empty otherwise). The model's tool rounds
  are never listed. A card a slice put into the thread (a digest's "Make a task", AG-R2) joins the answer it belongs
  to in `actions` and the inbox, with no run.
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

- A regenerate or an edit sends the question's text as well (the edited text for an edit); naming both is `422`.
- `upload_ids` (agent step 12b): ready uploads of purpose `leo_attachment` (files' presigned uploads, ≤ 10 MiB each),
  at most five, each once, only with a new question (`422` with a regenerate or an edit). An upload that is not the
  person's, not ready or of another purpose is `409 upload_not_claimable`. Each file is read as a step of the turn
  (`activity: read_attachment`, `detail`: the file's name): an image goes to the model beside the question; a
  document's text (PDF, DOCX, XLSX, PPTX, RTF, TXT, MD, CSV, JSON, XML, YAML — ≤ 64 K characters a file, ≤ 256 K a
  question) is read and kept, and a file that cannot be read fails its step alone with a code (`unsupported`,
  `malformed`, `encrypted`, `too_large`, `timeout`, `gone`, `unavailable`, `failed`). The question lists its
  attachments in the history (`attachments: [{id, name, size, type}]`).
- `surface.path` is the cabinet path without its query; Leo is told the page and, through the subject's owner, what
  the person may read of the meeting, task, board or file it shows — nothing about one they may not read.
- `regenerate_of` answers the last question again; `edit_of` replaces its text and its answer. Any other id is
  `409 not_last_question`.
- A busy thread answers `409 thread_busy`; `supersede: true` stops the running answer first.
- The same `Idempotency-Key` again streams the same run from its first event.
- Refusals before the stream: `402 token_limit` (`params.limit`: `frontier_weekly_tokens`, `standard_daily_tokens`,
  `standard_weekly_tokens`), `403 consent_required`, `404 thread_not_found`, `409 thread_busy`, `422`,
  `429 rate_limited | too_many_runs | agent_busy` with `Retry-After`, `503 agent_unavailable | entitlements_unavailable`.
- Resume: `GET /v1/agent/runs/{id}/events` with `Last-Event-ID`; `410 run_events_gone` once the log is gone — an
  hour after its last event, ten minutes after the run's end — reload the thread. Stop: `POST /v1/agent/runs/{id}/cancel` (202; asking again, or after the end, changes nothing). Another
  person's run is `404 run_not_found`.
- A run whose worker was lost ends `run.failed {process_lost}` within a minute; the question stays in the thread, so
  "Retry" asks it again.

### Stream events

Every event has a monotonic `id`; a comment line every 15 s keeps the connection open. Unknown event types are
ignored. Exactly one of `run.completed` and `run.failed` ends a run.

| Event | Data |
| --- | --- |
| `run.started` | `{run_id, thread_id, message_id, reply_id}` |
| `step.started` / `step.completed` / `step.failed` | `{id, seq, activity, detail?, duration_ms?, code?}` — `activity` is a tool's name (`notes.search`) or `think`, `write_answer`, `read_attachment`; an unknown one reads as a generic line |
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
LeoSource = {id, kind: meeting | file | task | note | mail | web | report, title, space, locator | null, quote, highlight: string[]}
```

The answer cites `[n]`, the n-th source counting from one. Sources come from the tools Leo used, never from the
model; `space` is "Personal" in the person's language or the workspace's name. A page `web.search` found
(agent step 13) is a `web` source: `id` is the page's `http(s)` address, `space` its site, `locator` null, `quote`
the passage used; the cabinet opens it in a new tab, and only at an `http(s)` address. Once the run has read text from outside, a `web.search` call is a card like a write (`tool: web.search`, `reversibility: irreversible`, a warning, its query as the one field); approved, the search runs and the epilogue answers from its pages. `highlight` stays empty for
now — the quote is shown whole. A marker for a number the list does not have is not drawn.

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

How the cabinet shows them (step 10):

- A turn ends at `run.paused`: its answer stays with the card, and the history, re-read, takes it over. A card shows
  in its answer once; a server note whose card already stands in its answer is not shown again.
- An approval follows `run_id` from its first event (`Last-Event-ID: 0`): the answer is rebuilt in place — the words
  before the card, the card's end, Leo's epilogue — and the history is re-read when the run ends. While the outcome
  is still on its way the server closes the stream at the card's pause; the cabinet reads it again with a growing
  pause for about three minutes. A pause on a new card of the epilogue ends the follow: that card is decided later.
- `action.updated` updates the card wherever it is shown (the panel, "Needs you"), and its `invalidates` re-read the
  shown screens of those domains — resources tagged with `inDomain` (`src/lib/resource-domains.ts`): `tasks` (boards,
  a task, Today), `notes` (the library, counts, a meeting, its notes, its share link, recent meetings), `files`
  (files, storage).
- `taint` and `outcome` are codes the cabinet words (`leoCards.card.taint`, `leoCards.card.outcome`); an unknown label
  reads as outside text, an unknown outcome adds nothing to the status.
- `409 action_not_pending` re-reads the card, which then shows how it ended.

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

`PUT /v1/agent/messages/{id}/feedback {rating: useful | not_useful}` → `{rating, shared}`; `DELETE` → `204`. A
question, a server note, another person's answer or a thread the person no longer sees is `404 message_not_found`. The
history's messages carry the person's rating in `feedback` (`useful`, `not_useful` or null).

One press under an answer, the same press again takes it back. The rating counts only in anonymous totals.
`shared` is true when the person's "Help improve the models" consent (Settings › Privacy) let the conversation become
an evaluation case — never for an answer built on a workspace's data.

## Leo in the admin panel

The admin's panel talks to the same routes under `/v1/admin/agent/*` — threads, history, turns, run events and
cancel, the same shapes — behind the admin's session cookie (ADR 0049), not a bearer token (agent step 16a). A
person's token opens none of them and the admin's cookie none of `/v1/agent/*`. The operator's threads are their
own (`scope=personal`); a turn takes no `upload_ids` (422 `attachments_not_allowed`) and is answered in Russian.
There are no cards, no ratings and no attachments. The operator's tools read platform aggregates — AI spend, the
OpenRouter balance, answer ratings, plans and promo codes, account counts — and cite them as `report` sources, whose
`id` names the report (`spend.summary:month:model`, `spend.daily:30`, `spend.forecast`, `openrouter.balance`,
`ratings:30`, `billing.plans`, `billing.promo_codes`, `identity.accounts:30`) and whose `space` is "Платформа". The
source's `title` is English (the model reads it); the admin's widget names a known report in Russian by its `id`
(`domain/report-titles.ts`) and falls back to the `title`. A series of at least two rows also comes as a `chart`
artifact — `{kind: "chart", ref: "chart:<report id>", alt, spec: {shape: bar | line, x, stacked, series: [{key,
label}], rows}}`, at most 100 rows computed by the tool, every day of a daily series present (a day without calls is
0) — which the admin's widget draws, with a table of the same rows a click away; a person's panel never receives one.

In the cabinet the admin panel's Leo is `AgentLeo` in the `platform` context (agent step 16c): `channelOf` picks the
operator's routes, no attachments and no rating buttons, and its panel never reads Settings › Leo (a person's): voice
mode is on and the answer is read out in the admin panel's language.

