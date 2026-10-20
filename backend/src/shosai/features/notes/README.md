# notes

Every recorded meeting becomes something the person never has to hold in their head: the transcript with speakers, Leo's write-up by a template, the findings with their evidence, the mind map, the person's own notes synced with the desktop, folders and one share link. The slice owns the meeting's life from start to processing — also when the client never says it ended — and the transcript store the live capture writes through.

- Plan: [docs/plan/slices/notes.md](../../../../../docs/plan/slices/notes.md). Decisions: MT-D1…MT-D12 in the plan, [ADR 0056](../../../../../docs/adr/0056-meetings-lifecycle-notes-and-share-links.md) and, for the slice's name (`meetings` until 2026-10-20), [ADR 0057](../../../../../docs/adr/0057-notes-and-meetings-slice-names.md).
- Public surface: `contracts` (`LiveMeetings`, `TranscriptStore`, the `LiveSignal` port capture binds, `MeetingReader`, `MeetingFindings`, their types and errors) and `contracts.events` (`notes.meeting.ended`, `notes.meeting.notes_ready`, `notes.meeting.deleted`, `notes.meeting.restored`).

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

- `application/lifecycle.py` — the start (minutes and the Free device in the person's transaction, the device's previous meeting ended), the native `PATCH` and §10's end under the meeting's row lock: the first end wins, writes `notes.meeting.ended` and the one `live` run; a meeting not kept leaves only billing's tombstone.
- `application/minutes.py` — the `billing.meeting_minutes` binding: live meetings until now within 6 hours, ended ones by their seconds, hidden ones until their purge.
- `channels/http/native_sessions.py`, `channels/http/runs.py` — `POST /v1/sessions`, `PATCH /v1/sessions/{id}` in the draft's shapes; `POST /v1/me/sessions/{id}/end`, `GET /v1/me/runs/{id}`.

## Live transcript and sweeps (step 4)

- `application/live_transcript.py` — capture's `TranscriptStore`: the batch's facts in one call past row-level security (`meetings_live_facts`), personal lines in one transaction and each company's in its scope, replays ignored, refused and cut lines counted.
- `application/live_meetings.py` — capture's `LiveMeetings.bind` for `session.start`.
- `application/sweeps.py` — every minute per home: meetings silent 5 minutes after their last audio or 6 hours long are ended; ended meetings are settled — inv-6 against what capture showed, the run of a spoken live meeting whose end found no speech yet.
- `objectives.py` — `TranscriptLineLost` (inv-6) and `MeetingLeftUnprocessed` (inv-7), with runbook sections in `docs/runbooks/alerts.md`.

## Pipeline (step 5)

- `application/pipeline.py` — the engine: a delivery claims its stage under the run's lock and commits the running mark, the handler works without an engine transaction, a second transaction records the outcome, the next stage is sent after that commit.
- `application/stage_task.py` — `notes.run_stage` on the `meeting` queue; a retry rides the broker's back-off.
- `application/run_recovery.py` — every minute per home: stages lost or held past the hold limit are sent again; the oldest open run is measured.
- `objectives.py` — the post-meeting objectives; the `MeetingRunOld` ticket is in `deploy/observability/prometheus/rules/tickets.yml`.

## Notes (step 6)

- `application/findings_stage.py` — the transcript in one call, or in windows of whole lines overlapping by eight, asked at once; a window unreadable twice is lost (counted and logged), every window lost retries the attempt; exact repeats of overlapping windows are kept once, then one merging pass; written once per run.
- `application/write_up_stage.py` — the layout (a rewrite's copy, the meeting's template, or Leo's), the summary from the findings and the closing lines that fit, the other sections listing findings by id, the map; the notes, the meeting's revision and `notes.meeting.notes_ready` in one transaction, once per run.
- `application/notes_model.py` — calls through the AI port under `meetings:{run}:{stage}:{2n}`, a second asking under `2n + 1`; answers are JSON objects read by their Pydantic shape.
- `application/write_up_rewrites.py`, `channels/http/write_up.py` — `POST /v1/notes/{id}/write-up {template_id}`: whoever may manage the meeting, ten a minute, once per `Idempotency-Key`; the findings and their ids are kept.
- `infrastructure/prompts.py` — English instructions and answer shapes, registered in the model-facing test; the notes are written in the language most of the meeting is spoken in (MT-D9).
- `settings.py` — `NOTES_MODEL`, required outside development, and its fallback, until studio's `notes` role.
- Revision `d9f3b7a1c246` adds `meeting_processing_runs.layout` (a rewrite's template, copied at the request, since a person's template is readable only in their scope) and `meeting_notes.findings_run_id`.

## Library and a meeting's page (step 7a)

- `application/library.py` — `GET /v1/notes` as a keyset over the start and the id, newest first, narrowed to the owner's folder, their meetings in none, or a workspace; a meeting's page; rename by whoever may manage, filing by the owner of a personal meeting.
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
- `channels/http/my_notes.py`, `channels/http/folders.py`, `channels/http/templates.py`, `channels/http/library_models.py` — the routes; folders and templates are registered before `/v1/notes/{id}`.

## Deletion (step 8, MT-D8)

- `application/deletion.py` — the owner hides a meeting that is not live: out of every read at once, its share link gone, `notes.meeting.deleted`; its minutes stay counted.
- `application/hidden_meetings.py` — every hour per home, meetings deleted 7 days ago go with everything under them; billing's tombstone once; the runs' objects deleted after the commit (`infrastructure/run_objects.py`).
- `application/support_meetings.py`, `channels/http/admin_meetings.py` — support's audited page and restore, refused while identity's deletion window runs (`application/account_window.py`, `channels/subscriptions.py`).
- `channels/http/native_me_sessions.py` — the native rename and deletion.

## Imports and transcription (step 9a, MT-D10)

- `application/imports.py`, `channels/http/imports.py` — `POST /v1/notes/imports {upload_id}` (202): files' claim and the meeting (source `import`) with its run in one transaction; a repeat with the same upload answers the same meeting and run; 409 `upload_not_claimable`, 409 `meetings_not_kept`.
- `domain/recordings.py` — the allowed containers and audio codecs, the 6 hours, parts of at most 5 minutes ending in the latest pause after their first minute.
- `infrastructure/media_tools.py` — `ffprobe` and `ffmpeg` as subprocesses under `prlimit` (address space, CPU, open files), a wall-clock limit that kills the process group, `PATH` only, the `file` protocol only; a hostile file fails its call, never the worker.
- `application/intake_stage.py` — the header read before any decoder: `unsupported_audio_format`, `recording_too_long`, billing's `covers` (`upload_exceeds_minutes`); the meeting takes the recording's length.
- `application/transcribe_stage.py` — pauses found, parts cut to Opus, at most four asked at once under `meetings:{run}:transcribe:{n}`, segments moved by their part's start, the raw transcript kept for 72 hours (O4, `transient/transcript/{run}.json`); since step 10 the align stage writes the lines.
- `application/scratch.py` — the stage's scratch directory, the object streamed into it, removed whatever the end.
- `stage_wiring.py` — a process runs the recording's stages only with `NOTES_TRANSCRIBE_MODEL`, `NOTES_DIARIZE_MODEL` and the tools on its path.

## The native import (step 9b)

- `channels/http/native_import.py` — `POST /v1/me/sessions/import` (multipart `file`, 202 `{jobId}`, ten a minute per person) and `GET /v1/me/sessions/import/{job_id}` (`{id, fileName, stage, progress, meetingId, error}`) in the draft's shapes; the refusals keep the draft's order and `detail`: 422 `import_unavailable_no_logs`, 402 `minutes_exhausted`, 422 `unsupported_audio_format`, 422 `empty_file`, 413 `file_too_large`.
- `channels/http/form_stream.py` — the body parsed as it arrives (python-multipart): the file field's headers, then its bytes; the rest drained before a refusal is answered; a client gone mid-body is 400 `request_incomplete` with its upload aborted.
- `application/native_imports.py` — the refusals before any row, the file streamed to `transient/import/{id}` in parts of 5 MiB (at most sixteen at once per process, 503 `imports_busy` after ten seconds' wait), then the meeting and its run (`application/import_rows.py`, shared with the cabinet's import); the object goes when the rows cannot be written.
- `application/import_jobs.py`, `domain/native_import.py` — the job is the person's own import run: `uploading`, `transcribing`, `enhancing`, `ready`, `failed`, with the share of its stages finished, both only growing; `channels/http/native_import_texts.py` words a failure in the person's language.
- Revision `a8f5b3482221` adds `meeting_processing_runs.source_filename`, the name the file came with.

## Diarization and alignment (step 10, MT-D3)

- `application/diarize_stage.py` — the whole recording as mono Opus at 16 kHz, sent once to pyannote through the AI port (`meetings:{run}:diarize:0`, `ESSENTIAL`); the turns kept for 72 hours (O5, `transient/turns/{run}.json`). Not critical: a failed diarization leaves the transcript without speakers and the run partially completed.
- `domain/alignment.py` — each segment takes the voice whose turns cover most of it (turns looked up by 10-second buckets), voices numbered by first appearance in the text, the owner of a desktop recording the voice most over the live "me" lines.
- `application/align_stage.py` — the lines of about 10 seconds replace, under the meeting's lock and with fresh `seq`s, the lines the recording covers (live ones and an earlier recording's, over its span: it began `audio_lead_ms` before the meeting, speech before the meeting's start held at it); the meeting's speakers are written anew with their talk time; the line count follows. Lines of the run found written mean the stage ran; a recording without speech replaces nothing (`transcript_empty`).
- `settings.py` — `NOTES_DIARIZE_MODEL` (pyannote's `precision-3` by default in `.env.example`), required outside development.

## The desktop recording (step 11, MT-D3)

- `channels/http/native_audio.py` — `POST /v1/me/sessions/{id}/audio/init {filename, mimetype, audio_lead_ms?}`, `PUT …/{run_id}/part/{n}` (raw body, at most 10 MiB), `GET …/{run_id}`, `POST …/{run_id}/complete`, `DELETE …/{run_id}` in the draft's `UploadStateOut`; refusals keep the draft's codes (409 `private_meeting`, `no_upload`, `no_parts`, `bad_part`, `empty_part`; 413 `part_too_large`), a refused part's body is read to its end first.
- `application/recording_uploads.py` — the meeting owner's, on a live meeting kept; `init` idempotent per meeting (the one `recording` run, its open upload, a new one when it has none, or the receipt when the audio is bound); the state is the bucket's list of parts; `complete` assembles, binds and commits before it answers, then sends the intake when the meeting has ended.
- `infrastructure/part_links.py` — a part streamed to its presigned link, at most sixteen at once per process (503 `parts_busy` after ten seconds' wait).
- `application/run_recovery.py` — a recording's run waits, passed by, until its audio is bound and its meeting has ended; then the sweep starts it.
- `application/intake_stage.py` — a desktop recording's meeting counts the larger of the live and the recorded length once; only what the recording adds is checked against the minutes left.
- `application/write_up_stage.py` — a desktop recording rewrites only Leo's automatic write-up; the person's own notes are never written by a run.

## The native library and notes; no-logs (step 12, MT-D1, MT-D6, MT-D12)

- `channels/http/native_library.py`, `channels/http/native_shapes.py` — `GET /v1/me/sessions` (a bare array of the person's newest 200 meetings matching `status` and `q`, `limit` and `offset` within them), `GET …/{id}/full` (lines with their `seq` as string ids, speakers worded, the map in pre-order), `GET …/{id}/note` and `PUT …/note/draft` (the person's own notes beside Leo's write-up as Markdown and its action items) in the draft's shapes.
- `channels/http/native_words.py`, `native_words.json` — "Speaker N" and the write-up's headings in the 16 languages, the cabinet's own translations, kept equal by a test.
- `application/meeting_settings.py`, `channels/http/settings.py` — `GET` and `PUT /v1/notes/settings {keep_meetings}`; the native `/v1/auth/me` gets `no_logs` from it.
- No-logs (MT-D6): a meeting not kept stores no line, own notes, participant, finding, recording or import (409 `private_meeting`, 422 `import_unavailable_no_logs`); it is purged at its end with only its minutes kept.

## Share links and the public page (step 13, MT-D5, MT-D12)

- `application/share_links.py`, `channels/http/share_links.py` — `GET`, `PUT` and `DELETE /v1/notes/{id}/share-link` for whoever may manage the meeting: the first `PUT` gives a token, a change keeps it, the expiry is counted anew only when another is chosen; `DELETE` takes the comments with it; a meeting not kept has no link (409 `private_meeting`).
- `application/shared_links.py` — a token looked up in both homes at once past row-level security, the meeting read in its company's scope, the link checked again in its owner's; every link that does not open is the one 404 `share_not_found`, a silent home 503.
- `application/shared_pages.py`, `channels/http/shared.py`, `channels/http/shared_shapes.py` — `GET /v1/shared/{token}` (the write-up with its findings, participants, the transcript's first 3 000 lines when shown) and `GET`/`POST …/comments` (the newest 200; a name of at most 60 characters or a guest), sixty reads and six comments a minute per address; never an address, anyone's own notes or the audio; names, owners and the owner's voice only with names shown.

## Leo's read tools (step 14)

- `channels/agent_tools.py` — `notes.search`, `notes.get`, `notes.read_transcript`, `notes.list_findings`: English specs, results labelled `meeting:speech` (Leo §7.4, core's `ToolSpec.provenance`).
- `channels/agent_tool_reads.py` — each sees only what `visible_meetings` admits (a meeting the person may not read is `not_found`); a transcript page holds the lines that fit its 6 000-token budget and names where the next starts.


## Other slices' readers and identity's deletion window (step 15a)

- `application/meeting_reader.py` — `notes.meeting_reader` (`facts`, `transcript`, `readable`) and `notes.meeting_findings` (`of`), read in the caller's transaction from `visible_meetings` with a meeting not kept left out: the facts of a batch in three queries, transcript pages as spoken by the cabinet's cursor (1 to 500 lines), the current notes' findings in order; a meeting the viewer may not read is absent or `meeting_not_found`.
- `application/account_window.py` — identity's `deletion_scheduled` marks every personal meeting of the person (`sessions.account_hidden`, revision `d7fdb62f4fd0`) in the delivery's transaction, `deletion_cancelled` clears it, an older event changes nothing; a meeting made while the mark stands is made hidden. `visible_meetings` serves a marked meeting to nobody — its owner, a workspace it is shared in, Leo, the readers — and its link does not open; the pipeline and the sweeps still finish it, so a cancellation brings everything back unchanged.
- Waits (step 15b): the workspace data spec and handler on workspaces' registry (its step 11), the consumers of `workspaces.member.removed` and `.workspace.deleted`, and the account data's export narrowed to personal meetings — together with the first source of a workspace's own meetings, since every meeting is personal today.

## Leo's write tools (step 16)

- `channels/agent_write_tools.py` — `notes.move_to_folder`, `notes.regenerate_notes`, `notes.set_share_link`, `notes.revoke_share_link`: English specs with their reversibility and cost class; a folder is named as the person calls it (no tool lists folder ids), a template is a shipped one's code or the meeting's own.
- `channels/agent_tool_writes.py`, `channels/agent_link_writes.py` — `plan` reads the meeting the person may manage and freezes it; `preview` gives an `agent.notes.*` key with the title and what changes; `execute` runs in the meeting's scope through `ActionItems`, over the session-level services the routes call as well (`MeetingLibrary.file_in`, `WriteUpRewrites.start_in`, `ShareLinks.put_in` and `remove_in`); refusals are the closed set of tool errors.
