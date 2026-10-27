# meetings — slice plan

Prompt: [prompts/S-feature-slice.md](../prompts/S-feature-slice.md). Status: [STATUS.md](../STATUS.md). Slice card: [SLICE_MAP.md §4.2.24](../SLICE_MAP.md#24-meetings). Decision: [ADR 0072](../../adr/0072-meetings-slice.md). Named `rooms` until [ADR 0057](../../adr/0057-notes-and-meetings-slice-names.md) (2026-10-20): the backend slice takes the cabinet's name, and `notes` keeps recorded meetings.

`meetings` is Shosai's own video call:

- **Starting and joining.** "New meeting" opens a room at once, and the link is the invitation.
- **Running itself.** The call needs no care and ends by itself when everyone has left.
- **Notes by speaker.** Leo takes notes on the server, track by track, so each speaker is known without a bot, a desktop app or diarization (fr-16).
- **In the call:** chat, which stays with the meeting; reactions and raised hands, which are ephemeral; and a whiteboard whose picture ends up in the notes.
- **Kept from the draft:** recording and broadcasts (SM-8 as changed by the owner).
- **Screens it owns:** the cabinet's Meetings section, `/app/meetings`, which composes calendar's upcoming events, notes' recordings and this slice's live rooms; and the admin's LiveKit screen.

- **Status:** approved by the owner on 2026-10-27 with amendments ([ADR 0072](../../adr/0072-meetings-slice.md)).
  - MR-D1, MR-D8 and MR-D10's data source: as proposed.
  - MR-D2…MR-D7, MR-D9 and MR-D10's audit: amended by the owner.
  - MR-D11…MR-D14: added by the owner (§2).
  - Detailing the plan derived itself is marked *agent-derived*. The owner confirmed four of these points on 2026-10-27: notes by participant track (MR-D15), chat through the server with its flood limit (MR-D11), "one recording" meaning one video recording (MR-D14), and 6 video tiles on a wide screen with 2 on a phone (MR-D2).
  - The owner's order: part A, then B1–B3 at once (notes is ready for them), then the steps that wait for capture, calendar and knowledge.
- **Dependencies (STATUS.md):**
  - `files` and `notes` are `in progress`; `workspaces` (core) is `done`; `capture`, `calendar` and `knowledge` are `todo`.
  - Part A also needs additive contract steps in other slices:
    - files: an object egress wrote; an upload made for a room's owner;
    - billing: `room_participants` and the recording capability per plan;
    - notes and agent: steps B1–B3.
- **Philosophy check:**
  - One action starts a call. A link joins it, with no account and no app.
  - The call ends itself, and the notes appear in Notes with every speaker named, the chat's links and the board's picture beside them.
  - Nothing has to be tended: no room list to clean, no lobby to watch, no setting to find.
  - What runs on the server is visible to everyone in the call: the "Leo is taking notes" and "Recording" marks are shown before joining and during the call.
  - Video plays only where attention is: the people speaking and the people pinned.
  - Broadcasts and the board sit behind one button each and never get in the way of a plain call.

---

## 1. Facts this plan rests on

### 1.1 Inputs

| Source | Fact |
|---|---|
| [SLICE_MAP](../SLICE_MAP.md) §4.2.24, §2.2, §2.10, §3, §8.1 | **Scope:** the Meetings section (New meeting, Schedule in calendar, live meetings, joining, recent recordings from notes; Upload a recording stays in Notes); LiveKit rooms; recording; per-participant track egress to capture; the room owner's meeting with company access; the join links already sent; the admin's LiveKit screen; broadcasts and the whiteboard, their screens designed before their steps. Subtitles and the room AI panel are dropped. **Routes:** `/v1/meetings/*`, `/v1/admin/livekit/*`; externally `POST /v1/livekit/webhook`, `GET /j/{token}`, `/meet/{token}`, `/rooms/join/{token}`, `/live/{token}`. The Leo architecture §8.2 lists a `meetings` toolset |
| Target architecture | fr-10, fr-16. §4.2: LiveKit (SFU, egress, coturn) in the plane, pinned versions. §4.3: clients → LiveKit over WebRTC, connect within 10 s; egress → WS gateway as PCM over WSS, one track per speaker; on failure the room is recorded and analysed after the meeting. §10 "Room transcription", §11.2, §13.2, §16 (trace context through the egress stream), §18.2 (`livekit-api` 1.2.1, `livekit-protocol` 1.1.27), §22 (measurement gate: tracks per egress and per WS process). §4.2, §4.3, §13.2 and §18.2 are amended by ADR 0072 |
| Cabinet [`features/meetings`](../../../frontend/src/features/meetings) | The section runs on samples. **Model:** `Meeting {id, title, start, end, source (google_meet, zoom, teams, shosai, in_person, recording, upload), joinUrl, location, participants, recap, recording}`. **Filters:** all, upcoming, live, past. Join opens 10 min before the start and runs until the end, in a new tab. "New meeting" is a menu; it and Upcoming are hidden while `meetings` is in `config/unserved-slices.ts`. **There is no room page, no join page and no broadcast or board screen** |
| Cabinet [`features/admin-livekit`](../../../frontend/src/features/admin-livekit) | On mocks with `domain/contract.ts`: `GET overview` → server, stats, 24 h history, nodes, rooms, egress; `GET rooms/{name}` adds participants with device attributes, connection quality and tracks; `DELETE rooms/{name}` and `DELETE …/participants/{identity}` → 204. Polled every 10 s while the tab is visible |
| Contracts (D1) | **No native client calls this area.** macOS 1.4.5 and Windows 1.4.5 call no room, LiveKit, whiteboard or stream route. External routes: the four link paths and the webhook. Invitation links also went out in calendar emails |
| [DATA_MAPPING](../DATA_MAPPING.md) §5.21, §6 | `rooms` and `room_recordings` move with `invite_token`, `lk_room_name` and `egress_id` kept verbatim (R1). `video_admin_actions` goes to identity's audit log (ADR 0072). The kept `streams*` tables move and the knock and hand tables are dropped. `room_whiteboards` moves, with `files` as JSONB of at most 8 MB. Prefix O2 is `u-{owner[:8]}/rec-{id}/{lk_room}.mp4`. `calendar_events.meeting_room_id` points at `rooms` |
| Slices in this repo | **notes** ([plan](notes.md)): `sessions.source` gains `room`; its contracts have `LiveMeetings`, `TranscriptStore`, `LiveSignal` and `MeetingReader`, but no port for another slice's call, no track-file run, no chat and no board (B1–B3 add them). **capture:** the WS gateway's foundation (`core/web/sockets.py`); live transcription and track ingest are not built. **files:** `HeldObjects` takes uploads and File Manager files, not an object egress wrote. **identity:** `OperatorAudit.acted`. **billing:** `MinutesAllowance`, `MEETING_MINUTES`. **agent:** images reach the model only as a question's attachments (`run_attachments.py`) |
| This host (2026-10-27) | **Compute:** 4 vCPU; 7.7 GB of memory, ≈ 1.9 GB available; swap 4 GB, 97 % used. *Update, evening of 2026-10-27 (A2):* the host has 16 GB (15 991 MB, ≈ 7 GB available, swap 33 % used) — the owner's "16 GB later" has arrived, so A15 revisits the staging limits. **Network:** one public IPv4, 129.101.125.250; NGINX of the staging edge on 80 and 443; no host firewall (`ufw` inactive). **Neighbours:** staging, its observability and the local development stack share it. STATUS's note that the host grows to 16 GB has not happened on this machine |

### 1.2 The draft, for lessons

I read `/root/whisperer/backend/src/meetassist/`:

- `core/livekit/`, `services/livekit/`, `services/room_*.py`;
- `api/me_rooms.py`, `rooms_public.py`, `livekit_webhooks.py`, `admin/livekit.py`;
- `web_meeting.py`, `web_stream.py`;
- `features/stream/*`, `features/whiteboard/*`;
- the migrations of these tables, their tests, specs 066, 067, 072, 078, 079 and 080, and `deploy/livekit/`;
- the frontend's `features/rooms` (`hooks/useRoomChat.ts`, `ui/ReactionsOverlay.tsx`, `hooks/whiteboard/*`, `model/whiteboard/*`, `ui/whiteboard/*`, `hooks/attachBoardToMeeting.ts`).

| Draft fact or incident | Rule in v2 |
|---|---|
| Passes on a bare `user_id` made LiveKit drop the earlier session with `DUPLICATE_IDENTITY` when one person joined from two devices (c1a327e86, production 2026-08-02) | Identity is `<principal>__<8 hex>`, the principal a user id or `guest-<12 hex>`. Rights and bans are keyed by principal, and a change goes to every live session of that principal |
| The draft never called `CreateRoom`, so a still-valid token (3600 s) could revive a "closed" room. An admin's close left the row active. Removing someone banned nobody | `auto_create: false`; the server creates the LiveKit room with its limits; join passes live 10 min, and LiveKit refreshes a connected client's token itself; a close marks the row first; a removal writes a ban |
| The end of a call is `room_finished` (`departure_timeout` 60 s, `empty_timeout` 300 s), not counted departures. The sweep runs every 300 s as a singleton, closes 60 min after the room emptied, closes nothing while the SFU is unreachable, and never closes a room with a pending calendar event or a live broadcast (594bbe4cb) | Kept; the calendar guard is a port answered "no pending event" until calendar binds it (B5) |
| Recording started the egress **before** committing the row, so an early webhook was a no-op. Two starts could race. `EGRESS_LIMIT_REACHED` was unhandled and nothing reconciled | The row is committed `starting` before `StartEgress`; a unique partial index allows one active recording per room; every end state is handled; the sweep reconciles against `ListEgress` |
| Transcribing a recording loaded the whole 720p mp4 (≈ 1.4 GB/h) against a 256 MiB cap; speakers were diarization clusters | Notes never read video; they read the participants' track files (B1–B2), each speaker known |
| The room JWT (3600 s) was the Bearer for the board and the stream chat and was never refreshed | Meetings' own routes take a **room pass**: opaque, bound to room and principal, 12 h, renewable while the room is open |
| Only the host saw that recording was on | The marks (`notes`, `recording`) live in LiveKit room metadata; everyone sees them, and the join page shows them before entering |
| Chat (spec 072 US2): JSON over the data channel, reliable, peer-to-peer, never kept. Client caps: 2 000 characters, 200 messages, an echo kept locally. Messages with a topic were the board's and were ignored | The server relays and keeps chat (MR-D11); the caps stay; the topics stay separate (`chat`, `reaction`, `wb`, `wb.cursor`) |
| Reactions: six emoji (👍 ❤️ 😂 🎉 👏 😮), ≤ 8 characters, at most 40 on screen, gone after 4 s, a guest's data treated as untrusted | Kept, with a rate per sender (MR-D12) |
| The webhook pointed at a dead domain (032d2e35d); the twirp client lost a `/livekit` path prefix (b95eac735); `livekit.yaml` cannot expand `${ENV}` | LiveKit posts to the API on the plane's network; server calls use the internal URL; signalling has its own subdomain; the config is rendered from the environment |
| Static memory limits while egress concurrency scaled with cores led to OOM; unpublished TURN relay ports failed silently; images were `latest`; no TURN over TLS on 443 | Pinned images, hard limits measured on this host, the relay ports published and probed, TURN/TLS on 443 by SNI (MR-D14) |
| A fixed limit of 50 participants protected nothing when every person saw every video (≈ 2 450 subscriptions, 9–13 cores). Load was counted as `publishers × (participants − 1)` against 180 per core (190–280 measured) | 50 stays as the ceiling, but video plays only for the people speaking and the people pinned (§1.3); the admin screen and alerts count subscriptions per core |
| Invite token `token_urlsafe(9)`, 12 characters, never expiring, matched exactly (old 32-byte tokens work). `/meet/{token}` is canonical; `/rooms/join/` and `/j/` live forever. The preview is neutral, `noindex`, with no database read. 10 joins per minute per IP; `not_found` and `room_finished` are distinct | Kept; the edge sends the three paths to the cabinet's join page with the fragment |
| Streams: no RTMP, HLS or ingress. Audience `hidden` without publish rights. Chat, reactions and hands over HTTP. `SendData` on topic `stream`. Host, cohost and speaker roles. `speaker_limit` 10, maximum 20. Knock lives 10 min, a hand 20 min. Chat 5 per 10 s for the audience and 20 per 10 s for the stage; 10 reactions per 10 s. The `end` order: stop egress, announce, close the row, `DeleteRoom` | Kept for broadcasts (A12b) |
| Board: Excalidraw 0.18.1 with its Mermaid → Excalidraw dialog; patches every 80 ms on `wb`, cursors every 60 ms on `wb.cursor`, catch-up after a 2 000 ms hello; the lowest identity among the openers saves (2 500 ms idle, retry 5 000 ms); one JSONB row per room with `version` (409 `scene_stale`, 413 beyond 20 000 elements, 4 MiB or 8 MiB); fonts self-hosted under `/app/wb/`; the editor's 16 languages mapped; the board as a 10 fps screen track while recording (e63cb4ff6); a PNG to the person's files when recording stops (`attachBoardToMeeting.ts`); a tool registry `{id, icon, labelKey, Panel}` over a scene contract, its one tool the formula panel | Kept (MR-D13); the formula panel is not built, but the registry stays; the PNG after every call with a board, not only at a recording's stop |

### 1.3 Design point and the 50-participant calculation

**Share.** Shosai calls are 5 % of the 19 500 meetings a day; the owner accepts this as the starting point. With 4 participants and 45 minutes on average, that is ≈ 1 000 calls a day and ≈ 75 concurrent at the peak (45 000 room-minutes ÷ the 600-minute window × 2, as in §3).

**A 50-person call** (*agent-derived* values):

- the cabinet shows at most 6 video tiles (the speaker, recent speakers and the pinned);
- simulcast with dynacast, so publishers send only the layers someone watches;
- Opus DTX, so a silent open microphone sends almost nothing;
- about 2 people speaking at a time.

| Quantity | Everyone sees everyone (the draft) | Speakers and pinned only (ADR 0072) |
|---|---|---|
| Video subscriptions | 50 × 49 = 2 450 | 50 × 6 = 300, 250 of them at the small layer |
| Audio carrying sound | 49 × all who are not muted | 2 × 49 ≈ 100 |
| SFU traffic out | ≈ 1.8 Gbit/s | 50 × (1 × 1.2 + 5 × 0.25) Mbit/s + audio ≈ 0.13 Gbit/s |
| SFU traffic in | ≈ 0.1 Gbit/s | ≤ 6 publishers × ≈ 2 Mbit/s ≈ 0.012 Gbit/s |
| Cores at 180 subscriptions each | ≈ 14 | (300 + 100) ÷ 180 ≈ 2.2 |
| Track egress for notes | — | one per participant from their first unmute; light jobs, measured in B2 |

**At the design point:**

- 75 calls of 4 people: 75 × 4 × 3 ≈ 900 subscriptions ≈ 5 cores, ≈ 0.7 Gbit/s out.
- Each concurrent 50-person call adds ≈ 2.2 cores and 0.13 Gbit/s.
- A 16-vCPU node at 70 % would hold the 75 calls and about 2 large ones. The production machine is a separate decision before launch (MR-D14).

**Transcription:** about the call's length × $0.003, because only speech parts are transcribed per track. Transcribing every track whole would multiply that by the participant count.

**Staging budget on this host:** hard limits, with the memory limit equal to the swap limit so no LiveKit process swaps.

| Container | `mem_limit` | `cpus` |
|---|---|---|
| LiveKit | 512 MB | 1.0 |
| Its Redis | 64 MB | 0.25 |
| Egress | 1 GB | 1.0 |

- At most 4 participants per room.
- One video recording at a time, ≤ 30 min, at a 540p 15 fps preset, measured in A7.
- Local development, only during meetings sessions: LiveKit 384 MB and 0.5 CPU; egress 1 GB and 1.0 CPU, started only when ≥ 1.5 GB is available.
- **16 GB later; when they arrive, the staging limits are revisited** (the owner, 2026-10-27). Until then these limits hold, and every start of egress, on staging or in development, checks the available memory first.

---

## 2. Decisions (taken by the owner on 2026-10-27, ADR 0072)

| ID | Decision | Who |
|---|---|---|
| **MR-D1** | A room per "New meeting", one link. The room closes when the owner ends it or 60 min after the last person left, never while its calendar event is pending. A closed room's link shows "This meeting has ended" | owner, as proposed |
| **MR-D2** | The link admits directly, with no waiting room. The owner can remove a participant, and that principal cannot rejoin the room. **Up to 50 participants**, the ceiling from the owner's plan entitlement `room_participants`, capped by the platform's `MEETINGS_ROOM_PARTICIPANTS_CEILING` (50; 4 on staging). Video plays for the people speaking and the people pinned; the others are avatars: at most 6 tiles on a wide screen, 2 at phone width (proposed by the plan, confirmed by the owner). *Agent-derived:* a plan without a value takes the platform ceiling | owner, amended |
| **MR-D3** | Leo's notes are on by default. Everyone sees "Leo is taking notes". The owner's minutes count once per call. The owner may turn notes off for the room | owner, amended |
| **MR-D4** | Video recording on paid plans only, under the storage limit, as a File Manager file in Recordings; it does not feed notes | owner |
| **MR-D5** | No E2EE: it would make transcription, Leo's notes and recording impossible. Migrated E2EE rooms are closed at cutover | owner |
| **MR-D6** | The room page: the video grid of speakers and pinned people with avatars for the rest; microphone, camera, screen share; devices; participants; invite; the marks; **chat, reactions, raised hand** (MR-D11, MR-D12); the board; leave and end. Screens on mocks first, for the owner's approval | owner, amended |
| **MR-D7** | Broadcasts: up to 100 viewers; paid plans create and start; at most 10 speakers besides the host; a waiting room only when the host turns it on | owner, amended |
| **MR-D8** | Leo's `meetings` toolset: `list_live`, `start_call`, `end_call` | owner, as proposed |
| **MR-D9** | *Replaced by MR-D14* | — |
| **MR-D10** | Data from LiveKit's API and Prometheus; the admin's actions in identity's audit log, with no `video_admin_actions` table | owner |
| **MR-D11** | **Chat.** Over LiveKit's data channel with reliable delivery; kept with the meeting; links and important points go into Leo's notes. *Mechanism proposed by the plan, confirmed by the owner:* the client sends to meetings' route, which applies bans and limits (20 per 10 s per principal, 2 000 characters) and keeps the message for the call. The server publishes it to the room with `SendData` reliable on topic `chat`, carrying an id and a sequence; clients drop duplicates by id and read what they missed after a reconnect. At the call's end the chat passes to notes with the meeting; a call with notes off keeps none | owner |
| **MR-D12** | **Reactions and raised hand:** ephemeral, with flood protection. *Agent-derived:* reactions are lossy packets on topic `reaction` from the six emoji, ≤ 10 per 10 s per sender, enforced by the sender and again by every receiver, at most 40 on screen for 4 s. The hand is a participant attribute, lowered by its owner, by the room's owner or by leaving; receivers coalesce toggles to one per second | owner; mechanism agent-derived |
| **MR-D13** | **Whiteboard,** following the draft:<br>• **editor:** Excalidraw at its current stable version, loaded only when the board opens; its fonts served by the cabinet;<br>• **collaboration:** patches over the data channel merged with `reconcileElements`, cursors, catch-up of a late joiner;<br>• **saving:** by one participant, with a version and 409; limits of 20 000 elements, 4 MiB of elements and 8 MiB of images; the server never parses elements;<br>• **in recordings:** a video track while recording;<br>• **after the call:** the PNG through files into the owner's storage beside the recording; the picture in the meeting's notes and visible to Leo; indexed by knowledge's multimodal embedder;<br>• **tools:** the Mermaid import kept; no formula panel, but its tool contract kept.<br>Screens on mocks first | owner |
| **MR-D14** | **Hosting now:**<br>• **this host only.** TURN/TLS on 443 through NGINX stream with `ssl_preread` (`turn.shosai.tech` → LiveKit's TURN, the rest → the edge with the proxy protocol). DNS `rtc.shosai.tech` and `turn.shosai.tech` → 129.101.125.250 (the owner sets them);<br>• **staging:** 4 participants, one video recording at a time with a length limit (the one-recording rule counts video recordings only; participant track egress is bounded by the 4 participants and egress's limits — confirmed by the owner), hard `mem_limit` and `cpus`; 16 GB later, and the limits are revisited when they arrive;<br>• **exposure:** the host has no firewall, neither its own nor in the provider's panel. Only LiveKit's media ports (UDP 7882, UDP 3478, UDP 30000–30099, TCP 7881) and 443 through NGINX listen outside. LiveKit's API, egress, its Redis and everything else listen on loopback or the Compose network only. A15 checks this, and the staging runbook records it;<br>• **local:** LiveKit by Compose profile only in meetings sessions, egress only where recording or track egress is checked, both stopped at the session's end;<br>• **50 participants checked by calculation** (§1.3);<br>• **the production machine:** decided before launch;<br>• the 5 % share accepted; the key and secret generated into `/root/shosai/.env` (done 2026-10-27) | owner |
| **MR-D15** | **Notes by participant track** (refines the owner's "notes from the room's audio recording"). While notes are on, each participant's audio track is written to its own file by track egress, a light job with no Chrome. Notes transcribe the speech parts of each file with their offsets; the speaker is the participant, with no diarization. This replaces a mixed composite, which needs a Chrome per call and pyannote, and pyannote answers 402 on staging. Capture later streams the same tracks live (B4) | proposed by the plan, confirmed by the owner on 2026-10-27 |

---

## 3. Design

### 3.1 Layout

**Backend** — `backend/src/shosai/features/meetings/`:

- `domain/` — rooms, calls, principals, grants, ceilings, chat, recording and broadcast states; no framework;
- `application/` — services and ports;
- `infrastructure/` — the LiveKit adapter on `livekit-api`, repositories, metrics;
- `channels/` — HTTP, the webhook, tasks, the Leo tools;
- `contracts/` and `module.py`.

**Frontend** — `frontend/src/features/meetings/` keeps the section and gains `room/`, `join/`, `chat/`, `board/` and `broadcast/`.

- **Heavy modules load only where used:** `livekit-client` (current stable) only on the room and broadcast routes; Excalidraw (current stable, MIT) only when the board opens.
- **No `@livekit/components-react`:** the cabinet's design system draws the page.
- **The board's tool registry:** the draft's tool contract, with Excalidraw's own Mermaid dialog as the first entry.

### 3.2 Public surface

| Item | What | Consumers |
|---|---|---|
| `RoomLinks` port | the room of a calendar event: made for its owner, its link and its state | calendar (B5) |
| `PendingEvents` port (owned here, bound by calendar) | is a room's event still pending; "no" until bound | the sweep |
| Notes ports, owned by notes (B1, B3) | `RoomMeetings`:<br>• `.open(call)` — the owner's meeting `source=room` in the room's scope, with its participants as known speakers;<br>• `.add_tracks(meeting, files)` — the participants' track files;<br>• `.end(call)` — the meeting's run;<br>• `.attach_chat(meeting, messages)`;<br>• `.attach_board(meeting, file)` | meetings |
| Capture's track ingest, owned by capture (B4) | `WS /v1/ws/rooms/tracks` inside the plane: one participant's PCM per stream, bound by a signed one-time ticket | LiveKit track egress |
| files ports, additive (A7, A11b) | `HeldObjects.from_written(owner, key, size, purpose)` — an object egress wrote, adopted into the owner's storage; `Uploads.create_for(owner, purpose)` — an upload a room's participant makes into the owner's storage (the board's PNG) | meetings |
| billing, additive (A4, A7) | the plan's `room_participants` limit and its recording capability | meetings |
| agent, additive (B3) | a read tool's result may carry one image (≤ `MAX_IMAGE_BYTES`) to the model | notes' `notes.get` |
| Events | `meetings.call.started` (room, call, org), `meetings.call.ended` (room, call, seconds, participant count), `meetings.recording.ready` (recording, file); ids and counts only | proactive later |
| `AccountDataSpec("meetings")`, `WorkspaceDataSpec` | rooms, calls, bans, recordings, chat of open calls, boards and broadcasts: exported, erased and moved with the person or the workspace | identity, workspaces |
| Leo toolset `meetings` | MR-D8 | agent |

### 3.3 HTTP and LiveKit interface

| Route | Who | Notes |
|---|---|---|
| `POST /v1/meetings/rooms` | person | `Idempotency-Key`; the scope is Personal or a workspace; returns the room with its link (A1: the pass comes from the join, which the cabinet makes for the owner too) |
| `GET /v1/meetings/rooms?state=live` | person | the section's Live (cursor page) |
| `GET/PATCH /v1/meetings/rooms/{id}` | owner | title, notes on or off; another person's room is 404 |
| `POST /v1/meetings/rooms/{id}/end` | owner | close first, then stop egress, announce, `DeleteRoom` |
| `POST /v1/meetings/join/{token}` | anyone, 10 per minute per IP | optional sign-in; both homes in parallel; returns `{room, livekit_url, livekit_token (10 min), room_pass, role, ceiling, marks}`; refusals `not_found`, `room_finished`, `room_full`, `removed` |
| `POST /v1/meetings/passes/refresh` | room pass | renews while the room is open |
| `DELETE /v1/meetings/rooms/{id}/participants/{identity}` | owner | removal and ban; `PATCH …/participants/{identity}/hand` lowers a hand |
| `POST /v1/meetings/rooms/{id}/chat`, `GET …/chat?after=` | room pass | MR-D11; 429 with `Retry-After` over the limit |
| `POST/DELETE /v1/meetings/rooms/{id}/recording` | owner | MR-D4; 202, its state through room metadata |
| `GET/PUT /v1/meetings/rooms/{id}/board`, `POST …/board/picture` | room pass | the scene with `version`, 409 and 413; the picture's presigned upload into the owner's storage, replaced while the call goes on |
| `/v1/meetings/broadcasts/*`, `/v1/meetings/live/{token}/*` | host and stage; public viewers | A12b |
| `POST /v1/livekit/webhook` (E) | LiveKit | verified with the API key (a JWT over the body's hash), 401 otherwise; handles `room_*`, `participant_*`, `track_*` and `egress_*`; idempotent by room, participant and egress ids; heavy work goes to tasks |
| `/v1/admin/livekit/overview`, `GET …/rooms/{name}`, `DELETE …/rooms/{name}`, `DELETE …/participants/{identity}` | operator roles `platform`, `owner` | the cabinet's contract |
| `GET /meet/{t}`, `/j/{t}`, `/rooms/join/{t}` (E) | edge | 302 to `/app/meet/{t}` with the fragment, `noindex`; `/live/{t}` → `/app/live/{t}` |

**LiveKit's configuration:**

- `auto_create: false`. The server's `CreateRoom` sets `max_participants` (the ceiling plus egress), `empty_timeout` 300 s, `departure_timeout` 60 s, and the metadata `{v, room_id, marks}` (A1: without the owner's home, which participants would read).
- Media: one UDP port (mux) 7882, ICE over TCP on 7881, `node_ip` the public address.
- Embedded TURN: UDP 3478 with a relay range of 30000–30099, and TLS reached through the edge's SNI stream on 443.
- Its own Redis container, ephemeral and apart from Valkey.
- Prometheus metrics for F5.
- The webhook to the API on the plane's network.

**Egress jobs:**

| Job | Output | Step |
|---|---|---|
| Video recording | room composite to the owner's home bucket, S3 credentials per request, ADR 0055 key | A7 |
| Notes | track egress to an audio file per participant, `transient/room_tracks/{call}/{track}.ogg` in the owner's home bucket, deleted when notes' run ends (the 3-day rule is the backstop) | B2 |
| Live notes | track egress to capture's WebSocket | B4 |

**The edge (A14).** NGINX's `stream` block listens on 443 with `ssl_preread`:

- `turn.shosai.tech` passes through to LiveKit's TURN/TLS, which uses certbot's certificate, mounted read-only;
- every other name goes to the HTTP edge's internal listener with `proxy_protocol`; the HTTP edge reads the client address from it (`real_ip_header proxy_protocol`), so rate limits and logs keep the client's IP;
- `rtc.shosai.tech` is an ordinary HTTP server block proxying to `livekit:7880`.

### 3.4 Data (each home)

- `rooms`: `id`, `owner_id`, `org_id`, `title` (≤ 200), `lk_room_name` (unique, `r-<hex>`), `invite_token` (unique; 12 characters for new rooms, migrated verbatim), `state` (`open`, `closed`), `notes_on`, `closed_at`, `closed_by` (`owner`, `idle`, `admin`, `account`), `event_ref` (B5), `broadcast_id`, timestamps. Partial indexes on open rooms and on emptied open rooms.
- `room_calls`: `id`, `room_id`, `org_id`, `lk_room_sid` (unique: one row per LiveKit room instance), `started_at`, `emptied_at`, `ended_at`, `ceiling`, `meeting_id` (B2), `board_upload_id` (the latest picture), `peak_participants`.
- `room_bans`: `(room_id, principal)` unique, `banned_by`, `created_at`.
- `room_chat_messages`: UUIDv7, `call_id`, `org_id`, `seq` (unique per call), `principal`, `author` (≤ 100), `text` (≤ 2 000), `sent_at`. Kept for the call only: handed to notes at its end (B3) and then deleted in the same transaction; a call with notes off deletes it when it ends.
- `room_tracks` (B2): `call_id`, `principal`, `name`, `track_sid`, `egress_id` (unique), `s3_key`, `started_ms` (offset from the call's start), `state`.
- `room_recordings`: `id`, `room_id`, `owner_id`, `org_id`, `egress_id` (unique when set), `state` (`starting`, `active`, `ending`, `complete`, `failed`), `s3_key`, `size`, `duration_seconds`, `held_object_id`, `error_code`. A unique partial index allows one active recording per room.
- `room_whiteboards`: `room_id` PK, `elements` JSONB, `files` JSONB (≤ 8 MiB), `version`, `updated_by`.
- `streams`, `stream_members`, `stream_bans`, `stream_chat_messages`, as DATA_MAPPING §5.21 (A12b).
- Row-level security: company isolation on `org_id`, owner isolation for personal rows. The public join reads through a function of the tables' owner that answers only the room with that token.

### 3.5 Flows

1. **New meeting.**
   1. `POST /rooms` commits the room.
   2. The cabinet opens `/app/meet/{token}`.
   3. The join issues the pass and creates the LiveKit room with the owner's ceiling.
   4. `room_started` opens the call. With notes on, the call opens the owner's meeting (B2).
2. **Join.**
   1. The token is looked up in both homes.
   2. The join refuses a closed room, a hidden owner, a full room or a banned principal.
   3. A guest gives a name.
   4. The pass carries the role's grants.
3. **In the call.**
   - Chat goes through meetings and is published reliably to the room.
   - Reactions and hands stay between clients, under the flood rules.
   - The board's patches and cursors go peer to peer. One client saves the scene and, 30 s after the last change and on leaving, uploads the PNG (*agent-derived*).
4. **End.**
   1. `room_finished` sets `emptied_at` once and ends the call.
   2. With notes on, the call hands the chat, the board's latest picture (filed in File Manager beside the recording) and the track files to the owner's meeting, then ends it: notes' run starts (B2, B3).
   3. The room stays open for 60 min for a rejoin, which is a new call.
5. **Recording.**
   1. Checks in order: the owner, the room is open, the entitlement, storage, no active recording, the platform's concurrent limit.
   2. The row is committed, then `StartEgress` runs.
   3. The webhook or the sweep finalizes it, and the length limit stops it.
   4. The object is adopted into File Manager and `meetings.recording.ready` is emitted.
6. **Admin.**
   1. Overview from LiveKit's API and Prometheus.
   2. A close marks the row, then deletes the SFU room.
   3. A removal bans the principal.
   4. Every action is written through `OperatorAudit`.
7. **Account and workspace.**
   - In identity's deletion window, open rooms are ended and their links refused.
   - Erasure and transfer go through the registry.
   - A deleted workspace's rooms go with it.

### 3.6 Invariants and how tests prove them

| Rule | Proof |
|---|---|
| A closed room never opens again | a still-valid token after close, against local LiveKit |
| A banned principal is refused on every path (join, refresh, chat, board) | access tests per route |
| One active recording per room; one call per LiveKit room sid; webhooks replayed or out of order change nothing | property tests over event orders; a concurrent start |
| An egress row exists before its egress | the start fails the egress after commit; the sweep reconciles |
| The ceiling is the owner's plan value capped by the platform's | entitlement tests per plan, and LiveKit refusing the participant over the ceiling |
| Chat: one message per id, ordered by `seq`, never kept when notes are off, gone from meetings once notes hold it | property tests; a call with notes off |
| Company rooms and calls open only within their scope (inv-14) | workspaces' isolation kit on every read path |
| The join refuses the same way for an unknown token and a hidden owner's room | a test, as for notes' share links |
| inv-11 for recordings, board pictures and track files | adopted objects count in the owner's storage; deleting the file or the run deletes the object |
| inv-13 | no money ceiling ends a call or its notes; minutes are checked at the call's start only |

### 3.7 Monitors and telemetry

- **Metrics `shosai_meetings_*`:**
  - rooms and calls by state;
  - joins by outcome;
  - chat messages and refusals;
  - webhooks by type and verification;
  - egress by kind and end state;
  - sweep closes;
  - subscriptions per core.
- **LiveKit's own metrics** go through F5's Prometheus.
- **Alerts:**
  - LiveKit not answering;
  - more than 5 % of egress failing in 15 min;
  - more than 1 % of webhooks failing verification;
  - a recording active without egress after 10 min;
  - subscriptions over 70 % of capacity;
  - LiveKit or egress near its `mem_limit`.
- **Probes:** the external probe checks the TLS of `rtc` and `turn`.
- **Logs** never carry tokens, passes, invite tokens or chat text.

---

## 4. Steps

**Skills.** Every backend step loads `fastapi` and `python-doctor`. The four Docker skills (`docker-project-foundations`, `docker-build-strategies`, `docker-compose-patterns`, `docker-destructive-guardrails`) load wherever a step touches Compose, migrations or tests against containers. Every cabinet step loads `vercel-react-best-practices`, `vercel-composition-patterns`, `vercel-react-view-transitions`, `web-design-guidelines` and `react-doctor` ("frontend ×5").

**Containers in a session (MR-D14).**

- A session that needs LiveKit starts the `meetings` profile (`docker compose -f compose.dev.yaml --profile meetings up -d`).
- It starts `meetings-recording` only for recording or track egress, and only with ≥ 1.5 GB available.
- It ends with `… --profile meetings --profile meetings-recording stop`, which stops the containers without removing them.

Every step ends releasable, with its gates at 100.

### Part A — now

| # | Step | Skills | Done when |
|---|---|---|---|
| A1 | **Contracts and domain.** Skeleton; the ports and events of §3.2. The domain covers room and call states, principals, grants per role, bans, ceilings, the idle rule, chat (ids, `seq`, limits), recording and broadcast states, and the invite token format. The OpenAPI paths of §3.3; the data-channel topics and their payloads as a documented contract (`chat`, `reaction`, `wb`, `wb.cursor`) | + `api-design` | Domain tests cover every state's exits; contracts reviewed **Done 2026-10-27:** `features/meetings` registered with its contract — `RoomLinks` (calendar's rooms), `PendingEvents` (bound by calendar, many bindings, none means no event pending), `meetings.call.started`, `.call.ended`, `.recording.ready` — and its domain: rooms (first close kept, a closed room never changed), invitation tokens (12 characters new, up to 64 kept), principals and per-session identities, display names without control characters or bidirectional overrides, the join's refusal order, the same SFU rights for everyone in a call, calls folded from webhooks (Hypothesis: any order and any replay fold to the same call), the sweep's verdicts, the chat's text, `seq` and packet, recordings moving only forward with the start's check order, broadcasts' states, entry and grants, and the room's metadata and attributes. The HTTP, metadata, attribute and topic contract is [frontend/docs/meetings-api.md](../../../frontend/docs/meetings-api.md). Agent-derived refinements: the room's metadata carries no `home` (participants read it; the webhook finds the room by its LiveKit name in both homes); `POST /rooms` answers the room and its link, and the pass comes from the join the cabinet's join page makes for the owner too; `room_finished` is 410, `room_full` 409, `removed` 403; the room pass travels as `X-Room-Pass`, apart from the person's own `Authorization`; a recording start also needs a live call (`409 no_live_call`). |
| A2 | **LiveKit locally and its adapter.** `compose.dev.yaml`: the `meetings` profile (LiveKit server and its Redis) and `meetings-recording` (egress), at pinned current versions, with the hard limits of §1.3 and the config rendered from the environment. Every published port is bound to 127.0.0.1, and the ports are its own, so development never collides with staging's public media ports and never listens outside; no TURN in development. `LIVEKIT_*` and `MEETINGS_*` settings documented. The adapter: server API on the internal URL, pass minting, webhook verification, health. Without LiveKit configured the app starts and the routes answer 503 `video_unavailable` | + Docker ×4, `resilience-failure` | Integration tests against the local server (create, pass, a test client connects, list, delete); a forged webhook is 401; the containers stopped at the end **Done 2026-10-27:** `LIVEKIT_*` (all four or none; `wss://` and a 32-character secret outside development) and the `VideoServer` port on `livekit-api` 1.2.2 — explicit values only, 5 s per call, one attempt, no Cloud failover; unreachable, timeout or 5xx → 503 `video_unavailable`, `not_found` an ordinary answer; passes for 10 minutes with the role's grants and the device attributes; webhooks verified by their JWT and the body's SHA-256 in constant time and read by a typed model (401 `webhook_rejected`); the `livekit` readiness probe and three metrics. `compose.dev.yaml`: `meetings` (LiveKit v1.13.11, its Redis 8.10.2) and `meetings-recording` (egress v1.15.0, started once to check it registers), on 127.0.0.1 only, on ports 17880–17882, with §1.3's limits and swap equal to memory; CI starts the profile. Against the local server: a room created once, a guest joins through signalling and is listed with its attributes, a deleted room is not revived by a still-valid pass (404), an unreachable server is 503; a forged webhook is 401. Agent-derived: the LiveKit tests are skipped without `TEST_LIVEKIT_*`, as the profile runs only in meetings sessions; egress reports "not enough cpu for some egress types" at 1 CPU (A7 measures and sets its CPU cost). |
| A3 | **Tables.** §3.4 except tracks and broadcasts, in each home, with RLS and the reading function; the account and workspace data specs | + Docker ×4, `data-storage` | Up and down in both homes; the isolation kit; export, erase and transfer cover every table **Done 2026-10-27:** the six tables of §3.4 in each home (migration `3b6722d0ad2b`), every child row carrying the room's owner and space; the company rule plus a restrictive owner rule for the application role, so a room is its owner's within the owner's spaces; `meetings_room_by_token` and `meetings_room_by_livekit_name` answer one room's id, owner and space; the sweep role reads rooms, calls and recordings; PostgreSQL keeps the closed sets, the token's and name's shapes, a close with its time and closer, one call per SFU sid, one `seq` per call, one active recording per room and the board's bounds. The account data handler exports, copies, compares, purges and erases the person's Personal rooms with everything they keep. Agent-derived: bans have a surrogate id (a unique key to page by); a workspace's room is the workspace's (nfr-16), as tasks decided — its `WorkspaceDataSpec` waits for workspaces to publish the contract. |
| A4 | **Rooms and joining.** Billing's `room_participants` limit (additive). Create (idempotent), live list, get, rename, notes on or off, end. The public join with both homes, limits and refusals; passes and refresh; removal with ban; lowering a hand; identity's deletion window | + Docker ×4, `api-design` | The access tests of §3.6; a closed room is not revived; two devices of one person stay; the ceiling holds per plan **Part A4a done 2026-10-27:** billing's `room_participants` (2–1 000, null for the platform's ceiling) in the catalogue, the snapshot and its cache (an older entry reads as null) and the admin's plan form; `MEETINGS_ROOM_PARTICIPANTS_CEILING`; the owner's `/v1/meetings/rooms` — create once per key in Personal or a workspace the person belongs to, the live list by cursor with the SFU's counts (null when it does not answer), read, rename, the notes switch (the SFU's marks first; 503 changes nothing) and end (closed first; the SFU room after, reconciled by the sweep if it did not answer). Agent-derived: A4 runs in three parts — A4a the owner's rooms, A4b the public join with passes and refresh, A4c removal with ban, the hand and identity's deletion window. **Part A4b done 2026-10-27:** the public join — both homes at once through the owner's function, ten a minute per address, the refusals that need no SFU before the SFU is touched, the first joiner creating the SFU room with the plan's ceiling capped by the platform's, `room_full` counted without egress, a LiveKit pass and an opaque room pass per session (two devices, two sessions of one principal) — and the pass's renewal while the room is open. Agent-derived: a hidden owner is a room closed by `account`; a home that does not answer makes the join 503 only when the other home has no such room. **Part A4c done 2026-10-27 — step A4 done:** removal bans the session's principal, revokes their passes and disconnects every session of theirs, the ban written first; the owner lowers a hand through the session's attributes; identity's `deletion_scheduled` and `blocked` queue a task that closes the person's open rooms in every space with `account` as closer and ends the SFU rooms after the commits. Two devices of one person stay two sessions (A4b); the ceiling per plan is tested at the join; the SFU calls are checked against local LiveKit. |
| A5 | **Webhook, calls and the sweep.** Calls from `room_started` and `room_finished`; the 300 s singleton sweep with the 60 min rule, "SFU unreachable closes nothing" and the guards (calendar's port unbound); `meetings.call.*` events; metrics | + Docker ×4, `task-scheduling`, `messaging-streaming`, `resilience-failure` | Property tests over webhook orders; the draft's sweep cases pass **Done 2026-10-27:** the signed webhook folds a room's events into its call — found in either home by its LiveKit name, opened once per sid with the instance's ceiling, the earliest start and the largest count kept, finished once — with `meetings.call.started` and `.ended` written once to the outbox and the handover queued as `meetings.hand_over_call`, which ends the call; the sweep of each home every 300 s closes nothing while the SFU does not answer, writes a lost finish, closes a room idle for an hour since its last call or since opening unless its calendar event is pending, and ends closed rooms the SFU still holds; two metrics. Domain property tests (A1) and the webhook's order and replay test against the database cover the orders; the draft's sweep cases pass. Agent-derived: webhooks are folded inline (a few statements) rather than queued, and only the handover is a task; a closed room still held by the SFU is ended by the sweep, which also reconciles an end or an account's close the SFU missed. |
| A6 | **Chat.** The chat route with bans, the GCRA limit (20 per 10 s per principal) and 2 000 characters; storage per call; `SendData` reliable on topic `chat` with id and `seq`; history after a sequence for a late joiner or a reconnect; erasure at the end when notes are off | + Docker ×4, `api-design`, `resilience-failure` | Two test clients receive every message once, in order, across a reconnect; 429 over the limit; a banned principal is refused **Done 2026-10-27:** the chat route with the room pass (room open, principal not removed, the pass's own room), a live call, 1–2 000 characters and the GCRA of 20 per 10 s per sender and room; kept once per key under the next `seq` with the call's row locked (thirty concurrent messages are numbered without gaps), published reliably on topic `chat` after the commit, and read after a `seq` for a late joiner or a reconnect; the handover deletes the call's chat. Agent-derived: until notes take the chat (B3), it is deleted at every call's end, notes on or off — kept no longer than the call; LiveKit answers `SendData` to a room no node holds as unavailable, so a missed packet is read back by `seq` rather than retried. |
| A7 | **Video recording.** files' `from_written` (additive) and billing's recording capability (if missing). Start and stop with the checks in order; the row before the egress; every end state; reconciliation in the sweep; the platform's concurrent limit and length limit (1 and 30 min on staging); adoption into File Manager's Recordings; the marks in room metadata; CPU and memory per composite measured on this host at 540p 15 fps and 720p 30 fps | + Docker ×4, `resilience-failure` | A recording against local LiveKit and S3 lands in File Manager; failure, limit and busy paths tested; the measurement recorded in §1.3 **Part A7a done 2026-10-27:** files' `WrittenFiles` (additive: the person's file key, storage left, adoption as a File Manager file charged whatever the limit, `files.file.uploaded`); start and stop with the checks in the domain's order, the row committed before a room composite (960×540, 15 fps) writes straight to the owner's file key in their home bucket with the request's credentials, the marks, reports only forward, the first `complete` adopted with `meetings.recording.ready`, failures with their codes, the sweep's length limit and settling of a lost webhook; `MEETINGS_RECORDINGS_CONCURRENT`, `MEETINGS_RECORDING_MAX_MINUTES`, `MEETINGS_EGRESS_S3_ENDPOINT_*`. Agent-derived, for the owner: "paid plans" is the snapshot's `paid`, with no new capability; the recording is the owner's personal File Manager file at the root, named after the room and its start — File Manager has no "Recordings" folder or video kind, and its folders are Leo's, so a "Recordings" place waits for the owner's word; the platform's running egresses are counted from the SFU. Part A7b — a live recording against local egress and S3 and the CPU and memory measurement — follows. |
| A8 | **Admin LiveKit.** `/v1/admin/livekit/*` for the cabinet's contract; Prometheus scrapes LiveKit, and the history and node queries read from it; close and remove through `OperatorAudit`; the cabinet's admin screen on the API, its mocks kept for tests | + Docker ×4, `observability` | The screen works against local LiveKit; every action is in the EU audit log; "no data" for history when Prometheus is down |
| A9 | **Room screens on mocks**, in the new visual language, on MSW mocks, for the owner's approval:<br>• the join page (guest name, devices, the two marks);<br>• the call: video tiles for the speakers and the pinned, avatars for the rest at 50; controls; participants with hands; invite; marks; the chat panel with unread counts; reactions; end;<br>• the states ended, full, removed, devices blocked, reconnecting and LiveKit unavailable;<br>• the "New meeting" menu (Start now, Schedule in calendar; Upload leaves it) and a live Shosai room in the section;<br>• the meeting page's chat and board sections in Notes (for B3);<br>• 16 languages, RTL | frontend ×5 | The owner approves; guidelines review clean |
| A10 | **Room page and section on the API.**<br>• `/app/meet/:token` standalone, signed in or as a guest;<br>• `livekit-client` loaded lazily, video subscribed only for visible tiles, device attributes set at join;<br>• chat on A6's route, reactions and hands by MR-D12;<br>• New meeting creates and opens the room;<br>• the section's Live from `/v1/meetings/rooms`, fetched in parallel with notes' recordings;<br>• `unserved-slices` split so New meeting shows while Upcoming waits for calendar;<br>• the edge's link redirects; CSP and `Permissions-Policy` for camera, microphone and screen | frontend ×5, Docker ×4 (edge) | A call between two browsers and a guest on local LiveKit with chat, reactions and hands; the bundle measured before and after (the room chunk only on its route); the old link paths land on the join page with the fragment |
| A11a | **Board screens on mocks.** The board in the call: open and close, collaborators' cursors, saved state, a conflict, the Mermaid import, read-only once closed | frontend ×5 | The owner approves |
| A11b | **Board.** files' `create_for` (additive). The scene route with the room pass, version and limits. Excalidraw loaded lazily, with self-hosted fonts and its 16 languages mapped. Sync over the data channel (`reconcileElements`, cursors, catch-up) with one saver. The tool registry with the Mermaid dialog. The board as a video track while recording. The picture uploaded into the owner's storage and filed beside the recording at the call's end | fastapi, python-doctor, frontend ×5 | Two clients draw and a late joiner catches up; 409 and 413 paths; the picture lands in File Manager; the room chunk is unchanged by the board |
| A12a | **Broadcast screens on mocks.** Studio (stage, speakers, start and end), viewer page `/app/live/:token`, waiting room, chat and hands, ended page | frontend ×5 | The owner approves |
| A12b | **Broadcasts backend.** Stream tables; roles by grants (audience hidden); lifecycle scheduled → live → ended with the draft's end order; knock, hands, chat and reactions over HTTP with their limits; `SendData` pushes; viewer count; MR-D7's limits | + Docker ×4, `api-design`, `resilience-failure` | Role and ban tests; 100 viewers checked by calculation and 4 by a test against local LiveKit |
| A12c | **Broadcasts in the cabinet.** A12a's screens on the API | frontend ×5 | A broadcast end to end in two browsers |
| A13 | **Leo's `meetings` toolset.** MR-D8's tools with plan, preview and execute through `ActionItems`; English descriptions registered in the model-facing test | + `agent-architecture`, Leo architecture §8 | A start and an end through Leo with approval; the model-facing test passes |
| A14 | **The edge's SNI split on 443.** NGINX `stream` with `ssl_preread`: `turn.shosai.tech` → LiveKit's TURN/TLS, the rest → the HTTP edge with the proxy protocol and the real client address; the security-headers gate; the edge's rollback rehearsed | Docker ×4 | Every existing route, rate limit and log line keeps the client's address; rollback in one command |
| A15 | **Staging.** DNS (`rtc` and `turn` → 129.101.125.250, set by the owner) and certificates. LiveKit, Redis and egress with MR-D14's limits. The ports published (UDP 7882, TCP 7881, UDP 3478, UDP 30000–30099). The staging ceiling 4 and one 30-minute recording. Release order; Prometheus scrape; probes. Calls from a Russian mobile network and from a network that blocks UDP. **Exposure check (MR-D14):**<br>• `ss -ltnup` on the host, and a scan from outside, find only UDP 7882, 3478 and 30000–30099, TCP 7881 and 443;<br>• LiveKit's API (7880), its metrics, egress and Redis are reachable only on the Compose network;<br>• the rule, the commands and the expected list go into [the staging runbook](../../runbooks/staging.md) | Docker ×4, `observability` | A call, a recording, a guest and chat on https://shosai.tech; TURN/TLS used when UDP is blocked; the host's memory stays above its alert; the outside scan matches the runbook's list; rollback rehearsed |
| A16 | **Contract verification.** The D1 gate for the slice's external routes; route and frame snapshots | fastapi, python-doctor | The four link paths and the webhook answer as the draft's consumers expect |

### Part B — notes right after part A, then the slices still to come

| # | Step | Waits for | Skills | Done when |
|---|---|---|---|---|
| B1 | **Notes: the room's meeting and track-file runs** (notes' step 27). `RoomMeetings.open/add_tracks/end`: the meeting `source=room` in the room's scope, its participants as known speakers (`meeting_speakers` by principal), the run of source `room`. The speech parts of each track file are cut by silence detection with their offsets, at most 25 MB a request, and transcribed; each line takes its participant as speaker; the lines are merged by time; no diarization; minutes once per call | notes (ready) | fastapi, python-doctor, Docker ×4 | A 3-track fixture becomes a transcript with three named speakers; silence is not sent; a no-logs or hidden owner gets nothing |
| B2 | **Meetings: track files for every call with notes on.** Track egress to an audio file per participant from the first unmute (`room_tracks`); the meeting opened at `room_started`, the files handed over and the meeting ended at `room_finished`; failure paths (an egress lost: the participant's lines are missing and the run is marked partial); notes off records nothing | B1 | fastapi, python-doctor, Docker ×4, `resilience-failure` | A 4-person call on staging becomes a meeting in Notes with each speaker named; the egress jobs per call measured on this host |
| B3 | **Chat and board into the notes** (notes' step 28, agent's addition).<br>• `attach_chat`: `meeting_chat_messages`, kept, exported, archived and erased with the meeting; the chat read by the findings and the write-up; a `link` finding kind for links shared;<br>• `attach_board`: the File Manager picture held by the meeting; a vision call describes it (an English prompt, registered) and the description joins the findings' input;<br>• the meeting page shows the chat and the board (A9's design);<br>• `notes.get` names both, and the agent's read tool result carries the picture to the model | B2 | fastapi, python-doctor, frontend ×5, `agent-architecture` | A call with chat links and a board gives notes with those links and what was on the board; Leo answers a question about the board; deleting the meeting deletes its chat and releases the picture |
| B4 | **Live notes per participant track.**<br>• Capture's ingest `WS /v1/ws/rooms/tracks`: tickets, one participant per stream, speech-only forwarding, `seq`, the transcript queue, drain into the owner's meeting;<br>• here: track egress to the WebSocket beside the file;<br>• the files kept as recovery, their run replacing live lines over the span they cover, as notes do for a desktop recording;<br>• the measurement gate of tracks per egress and per WS process | **capture** | fastapi, python-doctor, Docker ×4, `resilience-failure` | Live lines with named speakers in the meeting during the call; killing the WebSocket egress still yields notes from the files; the limits recorded in ARCHITECTURE §19 |
| B5 | **Calendar's rooms.** "Schedule in calendar" with a Shosai room through `RoomLinks`; `PendingEvents` bound; the section's Upcoming from calendar's events; invitation emails with `/meet/{token}`; M1's `calendar_events.meeting_room_id` | **calendar** | fastapi, python-doctor, frontend ×5 | A scheduled call appears in Upcoming, its Join opens 10 min before, its room survives the sweep until the event ends; `meetings` leaves `unserved-slices.ts` |
| B6 | **The board picture in knowledge.** The meeting's board picture indexed by knowledge's multimodal embedder, re-checked through `MeetingReader` (inv-10), dropped with the meeting | **knowledge** | fastapi, python-doctor | A search for what was drawn finds the meeting; a revoked reader does not |

---

## 5. LiveKit resources

**Settled by the owner on 2026-10-27:**

- this host only, with no second IPv4: TURN/TLS on 443 through the SNI split (A14);
- DNS `rtc.shosai.tech` and `turn.shosai.tech` → 129.101.125.250, set by the owner before A15;
- the LiveKit API key and secret generated into `/root/shosai/.env` on 2026-10-27;
- the production LiveKit machine decided separately before launch;
- the 5 % share accepted.

**Settled on 2026-10-27, second round:**

- **No firewall,** neither on the host nor in the provider's panel. Whatever a container publishes on `0.0.0.0` is public, so the exposure rule of MR-D14 is enforced by how each port is bound, and A15 checks it.
- **Memory: 16 GB later; when they arrive, the staging limits are revisited.** Until then MR-D14's limits hold. About 1.9 GB is available and swap is nearly full, so every session that starts egress (A7, A11b, B2) checks the available memory first.

**Found on 2026-10-27, outside the rule — for the owner:**

These sockets listen outside today, besides 443:

| Port | Process | Note |
|---|---|---|
| TCP 22 | `sshd` | the owner's and the release key's access |
| TCP 80 | the edge | the HTTP → HTTPS redirect and certbot's webroot renewal (`deploy/staging/certificate.sh`); closing it needs another ACME challenge |
| TCP 10050 | `zabbix_agentd` on `0.0.0.0` | probably the provider's monitoring agent |

A15 records them in the runbook as they are decided; this plan changes none of them.

**Not needed:** LiveKit Cloud, a separate bucket (egress writes into the home buckets), managed Redis (LiveKit has its own container), and anything for the shipped native clients.

---

## 6. Documents updated with the approval (2026-10-27)

- [ADR 0072](../../adr/0072-meetings-slice.md).
- ARCHITECTURE §4.2 (the edge's stream layer; LiveKit on this host), §4.3 (the participant bound; egress per track and to files), §13.2, §18.2.
- SLICE_MAP §4.2.24.
- DATA_MAPPING §5.21.
- The notes plan (steps 27 and 28 = B1 and B3).
- STATUS.md: `meetings` → `planned`.

Additive steps that later sessions write into their own plans: the files plan (`from_written`, `create_for`), billing (`room_participants`, the recording capability), and the capture plan, when written (B4's ingest).

## 7. Risks

- **WebRTC from Russian networks to the plane.** UDP may be throttled or blocked. TURN/TLS on 443 is the answer, checked on real networks in A15.
- **Memory on this host.** §1.3 and §5. The hard limits protect staging and development. A recording that hits its limit fails, and the person is told.
- **The SNI split puts every HTTPS connection through the stream layer.** A14 rehearses the rollback and checks that client addresses survive.
- **Prometheus metric names of the pinned LiveKit version.** A8 checks them; the panels show "no data" rather than guessing.
- **Guests' consent under Russian law.** The "Leo is taking notes" notice is the product mechanism; the legal wording waits for §22.
