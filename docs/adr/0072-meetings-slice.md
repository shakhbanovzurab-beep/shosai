# ADR 0072 — The meetings slice: Shosai's own calls on LiveKit, notes by participant, chat and board with the meeting

- **Status:** accepted by the owner on 2026-10-27 ([meetings plan](../plan/slices/meetings.md) §2).
  - MR-D1, MR-D8 and MR-D10's data source: as proposed.
  - MR-D2, MR-D3, MR-D4, MR-D5, MR-D6, MR-D7, MR-D9 and MR-D10's audit: with the owner's amendments.
  - MR-D11…MR-D14: added by the owner.
  - The points marked *agent-derived* are the plan's own detailing, stated so the owner can correct them.
- **Packages:**
  - `meetings` (owner);
  - notes (the room's meeting, notes from participant tracks, the call's chat and board picture);
  - files (objects egress writes, uploads made for a room's owner);
  - billing (the participant ceiling and the recording capability of each plan);
  - agent (an image in a read tool's result, the `meetings` toolset);
  - identity (`OperatorAudit` for the admin's actions);
  - capture (live track ingest);
  - calendar (rooms of events);
  - knowledge (the board picture indexed);
  - F4 (the edge's SNI split on 443);
  - M1 and M2.
- **Context documents:** [meetings plan](../plan/slices/meetings.md); [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.2, §4.3, §10, §11.2, §13.2, §18.2; [SLICE_MAP](../plan/SLICE_MAP.md) §4.2.24, §8.1 (SM-8); [ADR 0057](0057-notes-and-meetings-slice-names.md); [ADR 0043](0043-speech-providers-by-task.md); [ADR 0055](0055-object-key-layout-and-bucket-rules.md); [ADR 0064](0064-objects-other-slices-hold.md).

## Context

fr-10 and fr-16 make Shosai's own video calls core. The architecture placed LiveKit in the plane, with per-participant track egress to the WS gateway, 16 participants per room, and a whole-room recording as the fallback. The slice map kept broadcasts and the whiteboard (SM-8 as changed by the owner).

The new cabinet has the Meetings section and the admin's LiveKit screen on mocks. It has no room page, no join page and no broadcast or board screen. No native client calls this area; only the join links already sent and LiveKit's webhook are external contracts.

The draft taught several lessons:

- **Identities and rooms:** bare user ids as identities dropped a person's second device; a "closed" room could be revived by a still-valid token.
- **Recording:** a recording started before its row existed; composite video went into a transcription path capped at 256 MiB; speakers were diarization guesses.
- **Room UI:** only the host saw that recording was on; chat and reactions were peer-to-peer and never kept.

Two facts of today's host shape the rest:

- **One host for everything.** 4 vCPU, 7.7 GB of memory with about 1.9 GB available, and swap nearly full. There is one public IPv4, 129.101.125.250, and NGINX holds 443.
- **Speakers by pyannote fail on staging.** pyannote's staging key answers 402, so a recording diarized there gets no speakers.

## Decision

### Calls

1. **A room per "New meeting" (MR-D1).**
   - A room opens with one link and closes when the owner ends it, or 60 min after the last person left. It is never closed while its calendar event is pending or its broadcast is live.
   - A closed room's link answers "This meeting has ended".
   - LiveKit's auto-create is off. The server creates the LiveKit room, and a close marks the row before the SFU room is deleted, so nothing revives it.
2. **The link admits directly, with no waiting room (MR-D2).**
   - Signed-in people and guests (a name only) join directly.
   - The owner removes a participant, and that principal cannot rejoin the room.
   - An identity is `<principal>__<8 hex>`, so one person's devices never drop each other.
3. **Up to 50 participants, the ceiling from the plan (MR-D2, owner).**
   - The room's ceiling is the room owner's plan entitlement `room_participants`, capped by the platform ceiling `MEETINGS_ROOM_PARTICIPANTS_CEILING`: 50, and 4 on staging.
   - It is fixed when the LiveKit room is created; a plan change applies to the next call.
   - Video plays only for the people speaking and the people pinned; everyone else is an avatar.
   - *Agent-derived:* at most 6 video tiles on a wide screen and 2 at phone width; the cabinet subscribes to video only for its visible tiles, with simulcast, dynacast and Opus DTX. ARCHITECTURE §4.3's bound changes from 16 to this ceiling.
4. **Leo's notes are on by default (MR-D3).**
   - Everyone sees "Leo is taking notes" before joining and in the call.
   - The owner's monthly minutes count once per call, by its length; participants and guests pay nothing.
   - The owner may turn notes off for the room.
5. **Video recording on paid plans only (MR-D4).**
   - A room composite goes to the owner's home bucket, under the storage limit, as a File Manager file in Recordings.
   - Every participant sees "Recording".
   - The video does not feed notes.
6. **No end-to-end encryption (MR-D5).** It would make transcription, Leo's notes and recording impossible. Migrated E2EE rooms are closed at cutover.
7. **Chat in the call (MR-D11, owner).**
   - Messages travel over LiveKit's data channel with reliable delivery.
   - *Agent-derived:* the client sends through meetings' route, and the server applies bans and flood limits (20 messages per 10 s per principal, 2 000 characters), stores the message for the call, and publishes it to the room by `SendData` reliable on topic `chat` with an id and a sequence. A late joiner or a reconnect reads what it missed. The draft's peer-to-peer chat could be neither limited nor kept.
   - The chat is kept with the meeting. At the call's end it passes to notes, where it lives, is exported and is erased with the meeting. A call with notes off keeps no chat.
   - Links and important points from the chat enter Leo's notes.
8. **Reactions and raised hands are ephemeral, with flood protection (MR-D12, owner).**
   - Reactions are lossy data packets on topic `reaction` from the draft's fixed set of six emoji, at most 10 per 10 s per sender. Receivers drop anything outside the set or over the rate and show at most 40 at once, for 4 s each.
   - A raised hand is a participant attribute, so a late joiner sees it. It is lowered by its owner, by the room's owner or by leaving, and receivers coalesce toggles.
   - Nothing is stored.
9. **The whiteboard follows the draft (MR-D13, owner).**
   - **Editor:** Excalidraw at its current stable version, loaded only when the board opens. Its fonts are served by the cabinet, and nothing remote is loaded.
   - **Collaboration** over the data channel:
     - patches merged with `reconcileElements`;
     - collaborators' cursors;
     - a late joiner caught up by a participant who has the board open.
   - **Saving** by one participant, with a version and 409 on a conflict, and the draft's limits: 20 000 elements, 4 MiB of elements, 8 MiB of images. The server does not parse elements.
   - **Recording:** while a recording runs, the board is published as a video track so it is in the recording.
   - **After the meeting:** the board's PNG is saved through files into the owner's storage, beside the recording.
   - **New:** the picture enters the meeting's notes and Leo can see it, and knowledge indexes it with its multimodal embedder.
   - **Tools:** Excalidraw's Mermaid import stays. The formula panel is not built, but the board's tool contract — `{id, icon, label, Panel}` over the scene — stays, so the next tool is one entry.
10. **Broadcasts (MR-D7, owner).** Up to 100 viewers. The other limits are as proposed: paid plans create and start, at most 10 speakers besides the host, and a waiting room only when the host turns it on.
11. **Leo's `meetings` toolset (MR-D8).** `meetings.list_live`, `meetings.start_call` and `meetings.end_call`; the writes go through the Action Gateway.
12. **Admin (MR-D10).**
    - **Data:** rooms, participants and egress come from LiveKit's API; nodes and the 24 h history come from Prometheus, and that part shows "no data" when Prometheus does not answer.
    - **Audit:** the admin's actions go to identity's EU audit log through `OperatorAudit`. There is no `video_admin_actions` table; M1 copies the draft's rows to that log.

### Notes of a call

13. **Notes from the room's audio, right after part A (owner), by participant (agent-derived).**
    - **What is recorded.** While notes are on, each participant's audio track is written as its own file by track egress, from their first unmute. These are light GStreamer jobs, with no Chrome.
    - **How notes are made.** Notes transcribe only the speech parts of each file, cut by silence detection with their offsets. Each line takes its participant as the speaker, with no diarization.
    - **Why tracks rather than one mix:**
      - a mixed room composite needs a Chrome per call;
      - its speakers would be pyannote's guesses, and pyannote answers 402 on staging;
      - transcribing only speech keeps the cost near one track's.
    - **When capture ships**, the same tracks also stream live to the WS gateway (fr-16). The files stay as the meeting's recovery and its better transcript, as a desktop recording does for a live meeting in notes. They are transient objects, deleted when the run ends.

### Hosting now (MR-D14, owner)

14. **Everything on this host.**
    - **TURN/TLS on 443** through NGINX's stream module, routed by SNI (`ssl_preread`): `turn.shosai.tech` goes to LiveKit's TURN, and every other name to the HTTP edge, with the proxy protocol so client addresses survive for the rate limits and logs.
    - **Signalling** at `rtc.shosai.tech`. Both names point at 129.101.125.250.
    - **Staging limits:**
      - at most 4 participants per room;
      - one video recording at a time, with a length limit (*agent-derived:* 30 minutes, and a 540p 15 fps preset);
      - hard `mem_limit` (equal to the swap limit) and `cpus` for LiveKit, its Redis and egress.
      - *Agent-derived:* participant track egress for notes is bounded by the 4 participants and egress's container limits rather than by the one-recording rule.
    - **Local development:** LiveKit and its Redis run under a Compose profile only in meetings sessions, and egress under its own profile only in the sessions that check recording or track egress. Both are stopped at the session's end.
    - **50 participants** are checked by calculation, not on staging.
    - **The production LiveKit machine** is a separate decision before launch.
    - **The share of calls:** 5 % of meetings is the starting design point.
    - The LiveKit API key and secret are generated on the host.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Notes from a mixed whole-room audio composite (the plan's first B1) | A Chrome per call (≈ 75 at the design point), speakers by pyannote (402 on staging today), and a second mechanism beside the tracks capture will stream |
| Peer-to-peer chat, as in the draft | Nothing could be kept with the meeting, flood limits would be advisory, and a late joiner would see nothing |
| A lobby for guests | Every invitee waits and the owner has to watch it; MR-D2 keeps the draft's "conversation between equals" |
| A second IPv4 or port 5349 for TURN/TLS | The host has one address; networks that block everything but 443 would still fail on 5349 |
| Rendering the board's PNG on the server | The server would have to understand Excalidraw's elements, which it deliberately does not; the participant who saves the board exports it |

## Consequences

- **ARCHITECTURE:** §4.2 (the edge's stream layer, LiveKit on this host) and §4.3 (the participant bound, egress per track and to files) change with this decision. §13.2 now reads: when live egress fails, notes come from the track files. §18.2 gains `livekit-client` and Excalidraw.
- **Other slices gain additive contract steps:**
  - notes: the room's meeting, track-file runs, the chat and board attachments, a `link` finding;
  - files: an object egress wrote, an upload made for a room's owner;
  - billing: `room_participants` and the recording capability per plan;
  - agent: an image in a read tool's result.
- **Staging:**
  - the edge gains the 443 stream layer, with its own rollback;
  - LiveKit's memory and CPU are capped hard;
  - the host has little memory to spare (§1.3 of the plan).
- **The cabinet:**
  - `meetings` leaves `unserved-slices.ts` in two moves: New meeting and Live with this slice's API, Upcoming with calendar;
  - "Upload a recording" leaves the Meetings menu.
- **M1:**
  - rooms, invite tokens and LiveKit names are copied verbatim;
  - E2EE rooms are closed;
  - `video_admin_actions` rows go to identity's audit log.

## Revisit when

- Track egress or the WS gateway cannot hold one track per speaker at the design point (ARCHITECTURE §22's measurement gate).
- Broadcasts need more than 100 viewers — that means a measured node, or HLS.
- The production LiveKit machine is decided.
- The 5 % share is exceeded for a month.
