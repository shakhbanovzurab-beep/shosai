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

## Notes (step 6)

- `application/findings_stage.py` — the transcript in one call, or in windows of whole lines overlapping by eight, asked at once; a window unreadable twice is lost (counted and logged), every window lost retries the attempt; exact repeats of overlapping windows are kept once, then one merging pass; written once per run.
- `application/write_up_stage.py` — the layout (a rewrite's copy, the meeting's template, or Leo's), the summary from the findings and the closing lines that fit, the other sections listing findings by id, the map; the notes, the meeting's revision and `meetings.notes.ready` in one transaction, once per run.
- `application/notes_model.py` — calls through the AI port under `meetings:{run}:{stage}:{2n}`, a second asking under `2n + 1`; answers are JSON objects read by their Pydantic shape.
- `application/write_up_rewrites.py`, `channels/http/write_up.py` — `POST /v1/meetings/{id}/write-up {template_id}`: whoever may manage the meeting, ten a minute, once per `Idempotency-Key`; the findings and their ids are kept.
- `infrastructure/prompts.py` — English instructions and answer shapes, registered in the model-facing test; the notes are written in the language most of the meeting is spoken in (MT-D9).
- `settings.py` — `MEETINGS_NOTES_MODEL`, required outside development, and its fallback, until studio's `notes` role.
- Revision `d9f3b7a1c246` adds `meeting_processing_runs.layout` (a rewrite's template, copied at the request, since a person's template is readable only in their scope) and `meeting_notes.findings_run_id`.

## Library and a meeting's page (step 7a)

- `application/library.py` — `GET /v1/meetings` as a keyset over the start and the id, newest first, narrowed to the owner's folder, their meetings in none, or a workspace; a meeting's page; rename by whoever may manage, filing by the owner of a personal meeting.
- `application/library_cards.py` — a page's cards in four queries: notes, latest runs, the listed findings ranked per kind, the participants ranked per meeting.
- `application/meeting_content.py` — transcript pages (up to 500 lines, within the meeting's partition), the write-up with its findings inline, findings pages, map pages in pre-order.
- `application/visibility.py` — `meeting_scope`: a change is written in the meeting's own scope, since row-level security writes a company's row only there.
- `domain/reading.py` — the notes' state, who may file a meeting, the map as nodes.
- `channels/http/meetings.py`, `channels/http/meeting_content.py`, `channels/http/meeting_models.py` — the routes and their snake_case shapes.

## Own notes, participants, folders and templates (step 7b)

- `application/my_notes.py` — each reader's own notes on a meeting (MT-D12): `meeting_own_notes`, one row per meeting and person with row-level security by writer; nobody reads another's, the owner included; empty before a person writes; last write wins, the version grows in the same upsert.
- `application/participants.py` — add by address (a repeat answers the one there, at most 100), remove only those a person added; whoever may manage.
- `application/folders.py`, `application/templates.py` — a person's folders (the colour cycle, delete leaves meetings in no folder) and templates (shipped read-only, at most 50 own); creates take an optional `Idempotency-Key`.
- `application/library.py` — the template choice: a shipped one by any manager, the owner's own only by the owner.
- `channels/http/my_notes.py`, `channels/http/folders.py`, `channels/http/templates.py`, `channels/http/library_models.py` — the routes; folders and templates are registered before `/v1/meetings/{id}`.
