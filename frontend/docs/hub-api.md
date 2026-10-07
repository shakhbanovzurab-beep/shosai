# Hub API

The contract between the Hub screens (`/app/hub`, a meeting's hub on `/app/notes/{id}`, Leo inside a
hub) and the service that files meetings into hubs and finds what is missing in them. The TypeScript
types in `src/features/hub/domain/contract.ts` and `contract-threads.ts` are the source of truth.
Unlike the other contracts, field names are camelCase, as the Hub specification defines them.

The server owns every judgement: which hub a meeting belongs to, the topics, their stages, rounds
and gaps. The client only sorts by urgency and words what it is sent.

## Wiring

The browser only calls Next.js route handlers (`/api/hubs/*`, `/api/threads/*`, `/api/meetings/*`,
`/api/brief/today`). Each forwards the request unchanged to `${BACKEND_API_URL}/v1/…` when
`BACKEND_API_URL` is set (with `BACKEND_API_KEY` as a bearer token). Without it they answer from an
in-memory demo (`src/features/hub/server/`) that resets on restart.

The demo counts days from an injected "now" (`HUB_DEMO_NOW`, default `2026-10-06T15:00:00Z`), so its
states never drift. Its meetings are the sample recordings in Notes; quotes are read from their
transcripts. To see the screens' partial and failed states, set the cookie `hub_demo_fault` to
`partial` or `error` (the demo only).

Errors are `{"detail": {"code": "...", "message": "..."}}`. The UI shows its own text for the code,
never `message`. Codes: `name_taken`, `name_too_short`, `name_too_long`, `too_many_hubs`,
`not_found`, `hub_archived`, `invalid`; refusing to apply a task: `no_board`, `no_hub`,
`hub_archived`, `board_gone`, each with its own fix in the UI.

## Endpoints (prefix `/v1`)

| Method          | Path                              | Body                     | Response                         |
| --------------- | --------------------------------- | ------------------------ | -------------------------------- |
| `GET`           | `/hubs?include_archived=`         | —                        | `HubsResponse`, with each row's summary |
| `POST`          | `/hubs`                           | `{name}`                 | `201 Hub`                        |
| `PATCH`         | `/hubs/{id}`                      | `{name}`                 | `Hub`                            |
| `PUT`           | `/hubs/{id}/charter`              | `{purpose, success}`     | `Hub`                            |
| `PUT`           | `/hubs/{id}/board`                | `{boardId}`              | `Hub`                            |
| `PUT`           | `/hubs/{id}/archived`             | `{archived}`             | `Hub`                            |
| `DELETE`        | `/hubs/{id}`                      | —                        | `204`; meetings and documents stay |
| `GET`           | `/hubs/{id}/threads?state=open`   | —                        | `Loaded<ThreadSummary[]>`, one request per hub |
| `GET`           | `/hubs/{id}/digest/{sessionId}`   | —                        | `Loaded<Digest \| null>`; `latest` for the last meeting |
| `GET`           | `/hubs/{id}/feed?cursor=`         | —                        | `Loaded<FeedPage>`, 20 meetings a page |
| `GET`/`POST`    | `/hubs/{id}/materials`            | `{title, url}` or a multipart `file` | `Loaded<Material[]>` / `201 Material` |
| `DELETE`        | `/hubs/{id}/materials/{materialId}` | —                      | `204`                            |
| `POST`/`DELETE` | `/hubs/{id}/meetings/{sessionId}` | —                        | `MeetingHub`; filed by a person, remembered for the series |
| `POST`          | `/hubs/{id}/signal`               | —                        | `SignalResponse`; the assistant's signal, at most once a day |
| `GET`           | `/threads/{id}`                   | —                        | `ThreadDetail`                   |
| `POST`/`DELETE` | `/threads/{id}/done`              | —                        | `ThreadSummary`; `DELETE` undoes |
| `POST`/`DELETE` | `/threads/{id}/dismiss`           | `{gapKind}`              | `ThreadSummary`; off for 90 days everywhere; `DELETE` undoes |
| `POST`/`DELETE` | `/threads/{id}/abandon`           | —                        | `ThreadSummary`; `DELETE` undoes |
| `POST`          | `/threads/{id}/assign`            | `{owner}`                | `ThreadSummary`                  |
| `GET`           | `/meetings/{id}/hub`              | —                        | `MeetingHub`: the hub, or a suggestion with its signal |
| `GET`           | `/meetings/{id}/prep`             | —                        | `MeetingPrep \| null`            |
| `GET`           | `/meetings/prep`                  | —                        | `PrepResponse`: this week's meetings with a known hub |
| `GET`           | `/brief/today`                    | —                        | `Loaded<DailyBrief>`; empty is a valid answer |

Additions to the Hub specification, needed by the screens: `Hub.meetingCount` and
`Hub.agreementCount` (the hub page header), `Refutation.at`, `ThreadDetail.previousDecision` (a
reversed decision shown next to the current one), `Material.url` and `addedAt`, `MeetingPrep.meetingTitle`,
the feed's types, the signal endpoint, and `DELETE` on `done`, `dismiss` and `abandon` for Undo.

## Rules the UI relies on

- A gap's `days` are whole calendar days; `undated` is never sent as `overdue`.
- `circles` counts meetings a topic came back to without moving; the badge shows from 2.
- A dismissal hides the gap for 90 days from the rows, the hub's `topGap` in the list, the brief
  and the signal (the topic itself stays open). When it runs out and the gap comes back, `refutation.returned` is true.
- A meeting the server isn't sure about gets `suggestion`, never `hub`. A person's filing wins and
  applies to later meetings of the same calendar series.
