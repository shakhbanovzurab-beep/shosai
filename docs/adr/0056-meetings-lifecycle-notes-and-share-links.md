# ADR 0056 — Meetings: lifecycle, minutes, notes and share links

- **Status:** accepted by the owner on 2026-10-19 (meetings slice plan, decisions MT-D1…MT-D11 and the transcript's partition key; MT-D1, MT-D2, MT-D3, MT-D4, MT-D5, MT-D8 and MT-D10 with the owner's amendments).
- **Packages:** `meetings` (owner); capture (the live signal, the 6-hour warning), billing (minutes), workspaces (share records, auto-share), identity (`/v1/auth/me`, the deletion window, the operator audit), tasks (action items), site (the shared pages), M1 (data), M2 (the action-items route).
- **Context documents:** [meetings plan](../plan/slices/meetings.md); [ARCHITECTURE.md](../design/ARCHITECTURE.md) §7, §8.1, §9 inv-6, inv-7, inv-8, inv-13, §10, §11.3, §14 rules 1, 5, 6; [SLICE_MAP](../plan/SLICE_MAP.md) §4.2.5, SM-3, SM-5; [DATA_MAPPING](../plan/DATA_MAPPING.md) §5.4; [contracts/README.md](../../contracts/README.md); ADR 0007, 0043, 0054, 0055.

## Context

The shipped desktop clients start a meeting with `POST /v1/sessions`, end it only with `PATCH /v1/sessions/{id}` (no client sends the WebSocket `session.end`) and read legacy shapes: a bare array for the meeting list, camelCase notes. The draft copied the client's `ended_at`, so a client could erase its minutes; it closed silent meetings after 60 minutes without speech because it measured speech pauses up to 92 minutes; it kept three link visibilities with passwords that the new cabinet does not have; and it lost action items' ticks on every regeneration. The architecture asked for 5 minutes of silence, one page shape for every collection and monthly transcript partitions without naming their key.

## Decision

1. **API area (MT-D1).** The cabinet and Leo use a new area `/v1/meetings/*` (snake_case, ADR 0008, cursor pages). The native routes are a compatibility layer over the same services and keep their shapes; the native `GET /v1/me/sessions` stays a bare array with `limit` (1–200) and `offset` over the person's newest 200 meetings and gains no cursor. §10's `POST /v1/me/sessions/{id}/end` and `GET /v1/me/runs/{id}` are built as named.
2. **The end of a meeting (MT-D2).** The server decides `ended_at`: never before the last line, never after now or the meeting's start + 6 hours; a repeated end changes nothing. A meeting the client never ended closes 5 minutes after its last audio frame as capture sees it (a pause in speech never closes it). Every meeting lasts at most 6 hours: capture warns the person 10 minutes before and stops taking audio; an import over 6 hours is refused (`recording_too_long`).
3. **The desktop recording (MT-D3).** A live meeting's notes are written at once from the live transcript. When its recording arrives, the transcript is rebuilt with speakers over the span it covers, the findings are extracted again and Leo's automatic write-up is rewritten once; a write-up the person chose or regenerated and the person's own notes are never touched. A meeting counts its minutes once — the larger of its live and recorded length, at most 6 hours — and a recording that adds more minutes than are left is not processed (`upload_exceeds_minutes`). The upload is open on every plan.
4. **Action items (MT-D4).** They are tasks (SM-3). Until tasks ships they are findings without a checkbox; the native `PATCH …/note/action-items/{item_id}` is served by the tasks step and must be served before the cutover (M2).
5. **Share links (MT-D5).** One link per meeting, on or off, with the cabinet's settings (transcript, names, comments, expiry never, 7, 30 or 90 days); no password and no visibility levels; previews never show the title; one answer for every link that does not open. `/s/{token}` is the page and `/r/{token}` redirects to it. Migrated tokens stay; `private` and password-protected draft links are not carried.
6. **No-logs (MT-D6).** "Don't keep my meetings" stays, owned by meetings: the live transcript is shown and nothing is stored; minutes are still counted; imports are refused.
7. **Library (MT-D7).** Folders are flat and personal in five colours; tags, in-meeting answers (`prompt_executions`) and the draft's workspace impacts are not carried; import jobs fold into runs.
8. **Deletion (MT-D8).** As files' FL-D5: hidden 7 days, restorable by support, then purged with the minutes' tombstone; support neither lists nor restores an account's meetings in its deletion window, and every support action goes to the operator audit.
9. **Language (MT-D9).** Notes are written in the language most of the meeting is spoken in; shipped headings are worded by the cabinet.
10. **Media tools (MT-D10).** `ffmpeg` and `ffprobe` from the runtime image's Debian packages, as subprocesses with time and memory limits, without network, on an allowed list of formats checked before decoding.
11. **Plans (MT-D11).** Every plan gets the transcript, the write-up, the findings and the map.
12. **Transcript partitions.** `transcript_segments` is partitioned by the month of the meeting's start, so its unique key is truly `(session_id, seq)` and a meeting lives in one partition.
13. **Own notes per person (MT-D12, decided by the owner on 2026-10-19).** Whoever may read a meeting keeps notes of their own on it and sees and writes only those; nobody else's are shown to anyone, the meeting's owner included, and a share link never publishes them. The notes are `meeting_own_notes`, one row per meeting and person, with row-level security by writer; the native note routes read and write the current user's. A person who loses access keeps their notes, unreachable until access returns; they go with the meeting.

## Alternatives considered

| Alternative | Why not |
|---|---|
| The cabinet on `/v1/me/sessions/*` with a cursor added to the native list | The native list is a bare array: a cursor could only travel in a header no client reads, and the cabinet would inherit legacy shapes |
| Silence counted from the last phrase, after 60 minutes, as the draft | A forgotten recording runs an hour longer; the last audio frame tells a running recording from a stopped one |
| Keep the first write-up when the recording arrives | Action items keep the live "me / them" owners; the transcript with speakers would disagree with the notes |
| Keep passwords and three visibilities | No screen sets them; an unlock flow is another public surface |
| Partition by the phrase's start | A partitioned table's unique key must hold its partition key, so `(session_id, seq)` would not be unique across a month's end, and a meeting would span two partitions |
| PyAV in the worker process | A crash or a hostile file would take the worker down with it |

## Consequences

- Capture binds the live signal and sends the 10-minute warning; a shipped 1.4.5 client is warned only if a frame it already shows can carry it, and its meeting still ends at 6 hours.
- The runtime image grows by the media tools; meetings' step 9a measures it.
- Draft users lose their tags, the history of in-meeting answers and password-protected links; M1 counts them for the owner.
- §7, §8.1, §10 and §11.3 of the architecture, SLICE_MAP §4.2.5, DATA_MAPPING §5.4, the D1 README, STATUS and the M2 prompt were amended with the plan's approval.

## Revisit when

- A measured share of meetings ends by the 6-hour ceiling while people are still speaking.
- A company customer asks for password-protected links.
- Desktop clients that send `session.end` and their recording's offset replace 1.4.5.
