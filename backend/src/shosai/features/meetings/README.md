# meetings

Every recorded meeting becomes something the person never has to hold in their head: the transcript with speakers, Leo's write-up by a template, the findings with their evidence, the mind map, the person's own notes synced with the desktop, folders and one share link. The slice owns the meeting's life from start to processing — also when the client never says it ended — and the transcript store the live capture writes through.

- Plan: [docs/plan/slices/meetings.md](../../../../../docs/plan/slices/meetings.md). Decisions: MT-D1…MT-D11 in the plan and [ADR 0056](../../../../../docs/adr/0056-meetings-lifecycle-notes-and-share-links.md).
- Public surface: `contracts` (`LiveMeetings`, `TranscriptStore`, the `LiveSignal` port capture binds, `MeetingReader`, `MeetingFindings`, their types and errors) and `contracts.events` (`meetings.meeting.ended`, `meetings.notes.ready`, `meetings.meeting.deleted`, `meetings.meeting.restored`).

## Rules the domain holds

- `domain/meetings.py` — active until the client ends it, the silence sweep 5 minutes after its last audio, or 6 hours; the server's `ended_at` lies between the last line and the earlier of now and the 6 hours; a repeated end changes nothing; a meeting goes to processing when it is kept and something was said.
- `domain/minutes.py` — a meeting counts once: the larger of its live and its recorded length, at most 6 hours; what a recording adds is checked before it is processed.
- `domain/transcript.py` — a line is `(meeting, seq)` with the server's `seq`; equal texts are two lines; a rebuilt transcript takes fresh `seq`s; at most 2 000 characters a line.
- `domain/lines.py` — recognised pieces become lines of about 10 seconds, split at a sentence end or a pause, never over 60 seconds, 2 000 characters, another speaker or a gap over 800 ms; no text is dropped.
- `domain/runs.py` — a run's stages per source; three attempts per stage with pauses of 5, 30 and 120 seconds; failures retrying cannot help are not retried; critical and non-critical outcomes; terminal states are final.
- `domain/templates.py` — Leo's layout and the eight shipped templates by the cabinet's codes; a person's templates: name, description, icon, one to four sections of distinct kinds, at most 50.
- `domain/findings.py` — key points, decisions, action items, promises, risks and questions, each with evidence inside the meeting; due dates within a year of the meeting.
- `domain/mind_map.py` — the map projected from the findings: the title, up to six topics of two to five findings.
- `domain/sharing.py`, `domain/redaction.py` — one link per meeting with its settings and expiry, one refusal for every link that does not open, comments; a shared page never shows an address and numbers hidden speakers by first appearance.
- `domain/library.py` — flat folders in five colours, the person's own notes (last write wins, a growing version), participants by address.

## Tables (revision `a2c7e4f9b318`)

- `sessions` — the shareable `meeting` resource under company isolation; read only through `application/visibility.py`, never while hidden by a deletion.
- `transcript_segments` — partitioned by the month of its meeting's start, so `(session_id, seq)` is its unique key and a meeting lives in one partition; partitions are kept until the transcript archive.
- `meeting_speakers`, `meeting_participants`, `meeting_notes`, `meeting_findings`, `meeting_processing_runs`, `meeting_result_shares`, `meeting_share_comments` — under company isolation with `org_id` and the meeting's owner; they go with their meeting.
- `meeting_folders`, `meeting_templates`, `meeting_settings` — personal by nature.
- `meeting_object_deletions` — transient keys whose rows are gone, until the bucket confirms.
- `meetings_shared_meeting(token)` — the link's meeting and company, past row-level security, for a reader without an account.
- `application/account_data.py` — export, transfer and erasure: rows through core's helpers, the transcript meeting by meeting, transient objects by pointer.

## Lifecycle (step 3)

- `application/lifecycle.py` — the start (minutes and the Free device in the person's transaction, the device's previous meeting ended), the native `PATCH` and §10's end under the meeting's row lock: the first end wins, writes `meetings.meeting.ended` and the one `live` run; a meeting not kept leaves only billing's tombstone.
- `application/minutes.py` — the `billing.meeting_minutes` binding: live meetings until now within 6 hours, ended ones by their seconds, hidden ones until their purge.
- `channels/http/native_sessions.py`, `channels/http/runs.py` — `POST /v1/sessions`, `PATCH /v1/sessions/{id}` in the draft's shapes; `POST /v1/me/sessions/{id}/end`, `GET /v1/me/runs/{id}`.

## Live transcript and sweeps (step 4)

- `application/live_transcript.py` — capture's `TranscriptStore`: the batch's facts in one call past row-level security (`meetings_live_facts`), personal lines in one transaction and each company's in its scope, replays ignored, refused and cut lines counted.
- `application/live_meetings.py` — capture's `LiveMeetings.bind` for `session.start`.
- `application/sweeps.py` — every minute per home: meetings silent 5 minutes after their last audio or 6 hours long are ended; ended meetings are settled — inv-6 against what capture showed, the run of a spoken live meeting whose end found no speech yet.
- `objectives.py` — `TranscriptLineLost` (inv-6) and `MeetingLeftUnprocessed` (inv-7), with runbook sections in `docs/runbooks/alerts.md`.

## Pipeline (step 5)

- `application/pipeline.py` — the engine: a delivery claims its stage under the run's lock and commits the running mark, the handler works without an engine transaction, a second transaction records the outcome, the next stage is sent after that commit.
- `application/stage_task.py` — `meetings.run_stage` on the `meeting` queue; a retry rides the broker's back-off.
- `application/run_recovery.py` — every minute per home: stages lost or held past the hold limit are sent again; the oldest open run is measured.
- `objectives.py` — the post-meeting objectives; the `MeetingRunOld` ticket is in `deploy/observability/prometheus/rules/tickets.yml`.
