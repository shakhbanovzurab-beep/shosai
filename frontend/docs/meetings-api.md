# Meetings API

Shosai's own video calls on LiveKit ([ADR 0072](../../docs/adr/0072-meetings-slice.md)), on the backend's `meetings`
slice ([plan](../../docs/plan/slices/meetings.md) §3.3). This is the contract the room page, the join page and the
section's Live are built on; the routes arrive step by step (A4–A8, A11b, A12b) and their types then come from the
backend's OpenAPI (`src/lib/api/generated/schema.d.ts`). Errors use the backend's envelope (ADR 0008); the codes
below are the `code` the cabinet words through i18n. Times are ISO 8601 in UTC.

## Rooms (signed in)

| Method   | Path                                                   | Body                                   | Response     |
| -------- | ------------------------------------------------------ | -------------------------------------- | ------------ |
| `POST`   | `/v1/meetings/rooms` + `Idempotency-Key`               | `{"title"?: str, "workspace_id"?: uuid}` | `201 RoomOut` |
| `GET`    | `/v1/meetings/rooms?state=live&workspace_id=&cursor=&limit=` | —                                | `{items: RoomOut[], next_cursor}` |
| `GET`    | `/v1/meetings/rooms/{id}`                              | —                                      | `RoomOut`    |
| `PATCH`  | `/v1/meetings/rooms/{id}`                              | `{"title"?: str, "notes_on"?: bool}`   | `RoomOut`    |
| `POST`   | `/v1/meetings/rooms/{id}/end`                          | —                                      | `RoomOut`    |
| `DELETE` | `/v1/meetings/rooms/{id}/participants/{identity}`      | —                                      | `204`        |
| `PATCH`  | `/v1/meetings/rooms/{id}/participants/{identity}/hand` | `{"raised": false}`                    | `204`        |
| `POST`   | `/v1/meetings/rooms/{id}/recording`                    | —                                      | `202 RecordingOut` |
| `DELETE` | `/v1/meetings/rooms/{id}/recording`                    | —                                      | `202 RecordingOut` |

- **`RoomOut`** is `{id, title, state: open | closed, notes_on, workspace_id, link, created_at, closed_at,
  call: {started_at, participants} | null}`; whether a call records is in the room's marks.
  `title` is null for an untitled room (the cabinet names it); `link` is the full invitation,
  `https://shosai.tech/meet/{token}`; `call.participants` is null when the call server does not answer.
- **New meeting** creates the room and opens its `link` path in the cabinet (`/app/meet/{token}`), which joins like
  anyone else. The scope is Personal without `workspace_id`, or a workspace the person belongs to.
- **Only the owner** reads, changes, ends and records a room; any other room is `404 room_not_found`. The list holds
  the person's own rooms in the scope; `state=live` keeps those with a call going on (the section's Live).
- **End** closes the room for good and ends the call for everyone; ending a closed room answers it unchanged. A room
  also closes by itself an hour after its last call, never before its calendar event ends.
- **Removing** someone ends every session of that principal (signed-in person or guest) and they cannot rejoin the
  room (`403 removed`); the owner cannot remove themselves (`409 cannot_remove_owner`); an identity that is not a
  session of the room is `404 participant_not_found`. **Lowering a hand** is the owner's; the participant lowers their
  own through their attributes.
- **`RecordingOut`** is `{id, state: starting | active | ending | complete | failed, started_at, file_id | null}`;
  stopping without a running one is `409 recording_not_active`. The finished MP4 is the owner's File Manager file
  `"{title or Meeting} YYYY-MM-DD HH-MM.mp4"` whose id is `file_id`.
  Starting is refused in this order: `404 room_not_found`, `409 room_closed`, `409 no_live_call`,
  `403 recording_not_in_plan`, `413 storage_limit`, `409 recording_active`, `503 recordings_busy` (with
  `Retry-After`). A recording stops at the platform's length limit (30 minutes on staging); the finished file lands
  in File Manager's Recordings. Everyone sees that recording is on through the room's marks.
- `PATCH notes_on` turns Leo's notes off or on for the room from now; the mark changes for everyone.

## Joining (anyone with the link)

`POST /v1/meetings/join/{token}` — signed in or not, 10 per minute per address.

- **Body:** `{"name"?: str, "device"?: {os, os_version, client: web | desktop | mobile, client_version, browser}}`.
  A guest must give a name of 1–100 characters (`422 name_required`, `422 name_too_long`); a signed-in person
  joins under their profile name.
- **`200 JoinOut`:** `{room: {title, notes_on, recording}, livekit_url, livekit_token, room_pass, pass_expires_at,
  identity, role: owner | participant, ceiling, room_id | null}`. `room_id` is given to the owner only.
  `livekit_token` lives 10 minutes — enough to connect; LiveKit renews it while connected. `room_pass` lives
  12 hours and is sent as `X-Room-Pass` to the routes below.
- **Refusals:** `404 not_found` (no such link), `410 room_finished` ("This meeting has ended"), `403 removed`,
  `409 room_full` (the call has its `ceiling` of people), `503 video_unavailable` (calls are not available now),
  `429` with `Retry-After`.
- Each join is its own session: one person on two devices is in the call twice, as one principal.
- `POST /v1/meetings/passes/refresh` with `X-Room-Pass` answers `{room_pass, pass_expires_at}` while the room is
  open and the principal is not removed (`410 room_finished`, `403 removed`).

## In the call (`X-Room-Pass`)

| Method | Path                                         | Body                         | Response |
| ------ | -------------------------------------------- | ---------------------------- | -------- |
| `POST` | `/v1/meetings/rooms/{id}/chat` + `Idempotency-Key` | `{"text": str}`        | `201 ChatMessageOut` |
| `GET`  | `/v1/meetings/rooms/{id}/chat?after={seq}&limit=` | —                       | `{items: ChatMessageOut[], next_cursor}` |
| `GET`  | `/v1/meetings/rooms/{id}/board`              | —                            | `{elements, files, version, updated_at}` |
| `PUT`  | `/v1/meetings/rooms/{id}/board`              | `{elements, files, version}` | `{version}` |
| `POST` | `/v1/meetings/rooms/{id}/board/picture`      | `{size_bytes}`               | `{method, url, headers, expires_at}` |

- **Chat** (MR-D11): `MeetingChatMessageOut` is `{id, seq, identity, author, text, sent_at}`. The text is 1–2 000
  characters (`422 text_required`, `422 text_too_long`); 20 messages per 10 seconds per person (`429` with
  `Retry-After`); a call must be going on (`409 no_live_call`); a removed person is `403 removed`. The server
  publishes every accepted message to the room on topic `chat` (below), the sender's own included, so the sender
  shows it once by `id`. After a reconnect the client reads what it missed with `after` = the last `seq` it holds
  (`0` for all); a non-null `next_cursor` is the `after` of the next page. The chat stays with the meeting's notes
  after the call; with notes off it is gone when the call ends.
- **Board** (MR-D13, A11b): `MeetingBoardOut` is the scene as the editor saved it, its `version` (0 and empty
  before the first save) and `updated_at`. `PUT` needs a call going on (`409 no_live_call`); a stale `version` is
  `409 scene_stale` with the current one in `params.version`; more than 20 000 elements, 4 MiB of elements or 8 MiB
  of images is `413 scene_too_large`; 30 saves a minute per participant. `POST …/board/picture` answers a link to
  `PUT` the board's PNG (at most 25 MiB, exactly `size_bytes`) with exactly the given headers, straight into the
  owner's storage; each upload replaces the last, and when the call ends the last one becomes the owner's File
  Manager file. `413 storage_limit` when the owner's storage has no room; 6 links a minute per participant.
- **Broadcasts** (`/v1/meetings/broadcasts/*`, `/v1/meetings/live/{token}/*`) are specified with their screens (A12a).

## What clients read from LiveKit

**Room metadata** — JSON set by the server, read by everyone, shown before joining too:

```json
{ "v": 1, "room_id": "0199…", "owner": "0198…", "marks": { "notes": true, "recording": false } }
```

`marks.notes` is "Leo is taking notes", `marks.recording` is "Recording". `owner` is the room owner's principal: the
session whose identity carries it is the host — a participant's own attributes could not prove that. Clients take
`room_id` for the call's routes from here. Metadata of another shape is ignored.

**Participant attributes** — strings. `device.os`, `device.os_version`, `device.client`, `device.client_version` and
`device.browser` are set by the server from the join's `device`. `hand` is set by the participant when they raise
their hand (the time, ISO 8601) and removed when it is lowered — by them, by the owner, or by leaving. Receivers
coalesce a participant's hand changes to one per second.

**Identities** are `<principal>__<8 hex>`; the principal is a user id or `guest-<12 hex>`. Two identities with the
same principal are one person on two devices. Identities without `__` (egress) are not people: they are not shown.

**Data-channel topics** — JSON with a version `v`; an unknown `v` or a malformed packet is dropped:

| Topic       | Delivery | Sender            | Payload |
| ----------- | -------- | ----------------- | ------- |
| `chat`      | reliable | the server only   | `{v: 1, id, seq, identity, author, text, sent_at}` — dropped when it comes from a participant, or by `id` when already shown |
| `reaction`  | lossy    | a participant     | `{v: 1, emoji}` — one of 👍 ❤️ 😂 🎉 👏 😮; at most 10 per 10 s per sender, enforced by the sender and again by every receiver; at most 40 on screen, each for 4 s |
| `wb`        | reliable | a participant     | the board's patches, hello and catch-up (A11b) |
| `wb.cursor` | lossy    | a participant     | the board's cursors, at most one per 60 ms per sender (A11b) |

## Links

`/meet/{token}` is the canonical invitation; `/j/{token}` and `/rooms/join/{token}`, already sent by the earlier
product, keep working. The edge answers all three with `302 /app/meet/{token}`, keeping the fragment, and
`/live/{token}` with `302 /app/live/{token}`; none of them is indexed.

## Admin › LiveKit

`/v1/admin/livekit/overview`, `GET …/rooms/{name}`, `DELETE …/rooms/{name}` and
`DELETE …/rooms/{name}/participants/{identity}` (A8, MR-D10), behind the admin session; the types are
`LiveKit*Out` in the generated schema, aliased in `src/features/admin-livekit/domain/contract.ts`.

- Everything comes from LiveKit's server API and Prometheus, nothing from people's rows: a room is its LiveKit
  name (`r-…`), never a meeting title. LiveKit tells its API neither its version, a region nor a participant's
  connection quality, so the contract has none of them.
- The overview always answers: a LiveKit that does not answer is `health: "down"` with no rooms; a Prometheus
  that does not answer leaves `published_tracks`, the bandwidths, `nodes` and `history` as null or empty —
  "no data". A node Prometheus cannot scrape is `state: "down"` and the server `degraded`. A node's
  `memory_percent` is null until the deploy states LiveKit's memory limit (`MEETINGS_LIVEKIT_MEMORY_LIMIT_MB`).
- A participant's `device` is what their client declared at the join; an undeclared field is null.
- Ending a room closes it for good (`closed_by: admin`), then ends it in the SFU; removing a session bans its
  person or guest from the room (`banned_by: admin`) and disconnects every session of theirs. The room's owner is
  not removed (`409 cannot_remove_owner`). Each action is one row of the EU audit log, against the owner, naming
  the room. Errors: `room_not_found`, `participant_not_found`, `cannot_remove_owner`, `video_unavailable`.
