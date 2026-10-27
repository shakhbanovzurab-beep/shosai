# memory

What Leo knows about the person: their preferences, facts about them and their work, the people they deal with, their goals and how they work — each with its source, each visible, correctable and forgettable. Memory learns in the background from what the person says to Leo and from their meetings, puts the few facts that matter into a turn within a budget, and writes the overview the person reads in Settings › Memory.

- Plan: [docs/plan/slices/memory.md](../../../../../docs/plan/slices/memory.md). Decisions: MM-D1…MM-D8 in the plan and [ADR 0071](../../../../../docs/adr/0071-leo-memory-slice.md); the design is the [Leo architecture](../../../../../docs/design/leo/ARCHITECTURE.md) §7 with [ADR 0030](../../../../../docs/adr/0030-leo-memory-v2.md) and [ADR 0033](../../../../../docs/adr/0033-vectors-pgvector-for-memory-qdrant-for-knowledge-and-meetings.md).
- Public surface: the routes of §3.3 under `/v1/agent/memory` and the native `memory_enabled` of `/v1/auth/me`; memory binds the agent's `MEMORY_RECALL` and `PROFILE_FACTS` and reads the agent's `PERSON_WORDS` (`features/agent/contracts/memory.py`); it emits no event.

## Domain (step 1)

- **Facts** (`domain/facts.py`): kinds, sources, statuses and why a fact ended. A fact is current while active and not superseded; a candidate is never used. Editing supersedes — the old fact closes and names its successor — and a forget or a supersession made by the summary's box can be undone for 24 hours. Accepting, editing, pinning and the person's own settings confirm a fact; an explicit request in the person's own words is confirmed from the start.
- **Trust** (`domain/trust.py`, MM-D7): a confirmed fact raises no taint; any other keeps its source's taint, at least external. A meeting's fact is wrapped as `meeting:speech`, the rest as `memory`.
- **Decay** (`domain/decay.py`): half-lives by kind (fact and relationship 180 days, goal 30, preference and procedure 365), stretched by confirmations and doubled for an explicit request; pinned facts never fade; below 0.15 a fact expires. Recall never refreshes it.
- **What reaches a turn** (`domain/packing.py`): recall ranks current facts above the similarity floor (0.55, measured) by similarity × retention × confidence and packs ≤ 12 facts and ≤ 600 tokens, skipping what does not fit; the profile core takes pinned facts, then preferences by retention, within 400 tokens, listed by id so the block stays byte-identical.
- **Admission** (`domain/admission.py`, MM-D1, MM-D5): similarity says the subject, not the meaning — measured on `google/gemini-embedding-2`, a contradiction is as close as a rewording (plan §1.4). A statement in the same words as a current fact on its subject (≥ 0.87) confirms it; on the subject of a current fact it proposes to replace it; on the subject of a pending candidate it is not asked twice; on the subject of a fact the person forgot or turned down in the last 180 days it is never asked again unless asked for now. The rule: an explicit request is saved, anything else is a candidate, at most three new ones a day. Once `memory.admit` acts, a confident statement that is not sensitive is saved unconfirmed — one in twenty still asked — and the rest wait; a meeting's statement always waits; nothing is less careful than the rule.
- **Lifetimes** (`domain/lifetimes.py`, MM-D4, MM-D8): a workspace's facts erased 7 days after the person leaves, a deleted meeting's with its purge, a team chat's by the chat's retention; candidates leave after 30 days except the draft's carried-over ones; ended facts are purged after 180 days.
- **Summary** (`domain/summary.py`): one to five titled sections of plain prose and at most three suggested questions; markup, lists or repeats refuse a written summary.
- **The box** (`domain/box.py`, MM-D3): the model's reply resolved against the references it was given; forgetting wins over a correction of the same fact; limits on each kind of change.

## Tables (step 2)

- In each home (`infrastructure/records.py`, revision `e8bc01bd5bb4`): `memory_facts` — facts, candidates and ended facts with their `halfvec(1024)` stored `PLAIN` (no TOAST), the source's space, the source's taint and the person's confirmation; `memory_settings` — the switch, absent while on; `memory_summaries` — the overview as last checked. Row-level security admits the person's own rows; the sweep role reads facts and summaries for the daily upkeep. PostgreSQL keeps every closed set and the rules that tie a fact's columns together (a pinned candidate, a forgotten fact without its reason, a vector without its model are refused).
- Paths: the person's current facts through a partial b-tree (recall and the profile core read them exactly — at the 5 000-fact limit the database spends ≈ 14 ms, so no HNSW), lists by status and date, a thread's waiting candidates, `erase_after`, and the ended facts for the purge.
- The migration creates the `vector` extension when it is missing and drops it on the way down only if this role created it: a server whose owner installed it keeps it.
- Account data (`application/account_data.py`): every table is erased with the person; the export lists facts without their vectors; a transfer copies them with their vectors; the "has memories" bit in Valkey (`infrastructure/presence.py`) goes with the erasure.

## Settings > Memory's routes (step 3)

- `channels/http/facts.py`: `GET /v1/agent/memory` — candidates first, then current facts, newest first, by cursor, with the counts the settings row shows (`active`, `candidates`, `imported`) and filters on the server (`status`, `kind`, `source=imported`, `thread_id`, `q`); a meeting's fact names the meeting as notes titles it now for the person. `PATCH /{id}` — a new statement supersedes once per `Idempotency-Key` (the person's own words, confirmed, the pin kept), editing a candidate accepts it, a pin alone changes only the pin; `POST /{id}/accept` — accepting a candidate closes the current fact it proposed to replace; `DELETE /{id}` and `DELETE` (everything, the summary emptied, the bit cleared) are idempotent; `POST /imported/turn-down` (MM-D8); `GET`/`PATCH /settings` — the switch, whose moment is kept for the invariant monitor.
- What the person may see (`application/fact_rows.py`): current or waiting, not on its way to erasure, in Personal or a workspace they are in now (MM-D4). Anything else — another person's, a superseded, a left workspace's fact — is `memory_fact_not_found`.
- `MemorySwitch` contributes the draft's `memory_enabled` to the native `/v1/auth/me`.

## Vectors and recall (step 4a)

- `infrastructure/embeddings.py`: `google/gemini-embedding-2` through the provider port, 1 024 dimensions, a question as `task: search result | query: …`, a statement as `title: none | text: …`; every call the person's, under their consent, outside their Leo tokens; a question's cost row written off the turn's path.
- `application/embedding_pass.py` and `channels/tasks.py`: once a minute per home, facts waiting for the current model's vector — through the partial index `ix_memory_facts_unembedded` — person by person after the last one served, as the person; the vector lands only on the same statement, still waiting.
- `application/recall.py` binds the agent's `MEMORY_RECALL` and `PROFILE_FACTS`: no consent, a clear "has memories" bit, memory off, nothing held, late or failed all give nothing, counted in `shosai_memory_recall_total{outcome}`; otherwise the exact nearest 40, the floor, 12 facts and 600 tokens. The profile core is read in the agent's transaction: memory on or off, pinned facts and preferences.

## Admission from turns (step 5)

- `channels/subscriptions.py` sends `memory.admit_turn` for each `agent.turn.completed`; `application/turn_admission.py` reads the agent's `PERSON_WORDS` with the switch and the consent, asks `infrastructure/extractor.py` (`MEMORY_MODEL`, one more ask on an unreadable answer) for at most three statements, embeds them in one call, and `application/admission_writer.py` decides and writes under the person's admission lock, reading the switch again inside it. The write is keyed by the run; a suspicious run, memory off, the operator or a missing consent take nothing.

## Leo's `memory` toolset (step 6)

- `channels/agent_tools.py` declares `memory.recall` (read) and `memory.forget` (write, compensable), both behind the agent's `MEMORY_SWITCH`: a turn carries it only while the person's memory is on (read at the turn's start through `PROFILE_FACTS.enabled`). Never offered over MCP.
- `application/fact_search.py`: with a query, one embedding under the person's consent and the exact nearest 20 above the recall floor; without one, the pinned and then the most recently confirmed. Current facts in Personal and the workspaces the person is in now only. A result with a meeting's fact is labelled `meeting:speech` and cites the meeting the person can still read; any other `memory`. The result is wrapped whole, so it marks the run external even when every fact was confirmed.
- `application/fact_forgets.py` and `channels/agent_tool_handlers.py`: the plan freezes up to ten facts, every one current and the person's or the call is refused; the card (`channels/agent_previews.py`, 16 languages) shows how many and each statement as stored; the approved write ends those still current under row locks with the item's key and audit event (`ActionItems`), restorable for 24 hours, even if memory was switched off after the approval.

## The summary, its box and restore (step 7)

- `application/summaries.py` and `channels/http/summary.py`: `GET /v1/agent/memory/summary` never calls a model — the kept summary, when it was written, and whether it is stale: the digest of the current facts (`application/summary_facts.py`, one SQL aggregate) or the interface language changed since. A stale summary older than an hour is queued (`memory.write_summary`, once per ten minutes through a Valkey key); `POST …/refresh` writes it now, ten an hour. The writer reads at most 200 current facts, pinned first then by retention, as `F7 [kind] statement`; an empty memory writes an empty summary with no call; a summary that fails `domain/summary.py`'s checks is not kept. `shosai_memory_summary_writes_total{trigger, outcome}`.
- `application/box_messages.py` and `application/box_changes.py`: `POST …/summary/messages` — memory's own model call, once per `Idempotency-Key`, 30 an hour; the answer to a question, and the changes the message asks for under the person's admission lock — a remembered statement becomes the person's confirmed fact in Personal unless the same words are held, a correction supersedes, a forget ends — each returned with its fact and, for a correction, the fact it replaced. The summary is queued afterwards.
- `application/fact_restore.py`: `POST /v1/agent/memory/{id}/restore` — within a day of a forget or a replacement; a turned-down candidate comes back waiting; an expiry, forgetting everything or a replacement replaced again are final.
- `infrastructure/memory_model.py`: the extraction, the summary and the box share one call — a JSON object asked once more when unreadable.

## Meeting recollections (step 9)

- `channels/subscriptions.py` sends `memory.recollect_meeting` for revision 1 of `notes.meeting.notes_ready`; `application/meeting_recollection.py` reads the owner's switch and consent and the meeting through `MEETING_READER` and `MEETING_FINDINGS` as the owner, asks `infrastructure/recollector.py` for at most five statements, embeds them in one call and writes them through `application/admission_writer.py` as candidates in the meeting's space, labelled as its speech, each citing its finding or the summary. A statement about the owner needs evidence that names them (`domain/recollections.py`). The write is keyed by the meeting; a key already written answers before the model is asked.

## Upkeep and departures (step 8)

- `application/upkeep.py` and `channels/tasks.py` (`memory.upkeep`, every ten minutes per home): each person who holds a fact is tended once a day on the day's Valkey cursor, under their admission lock — faded facts and candidates unanswered for 30 days end as `expired` (pinned and carried-over ones never), facts ended or replaced over 180 days ago are purged, a stale summary is queued.
- `application/departures.py` and `channels/departure_events.py`: a workspace's departure marks the person's facts of it seven days on, its deletion erases them at once; a meeting's deletion marks its facts for its purge, its restore settles them; `memory.settle_marks` (hourly) erases a due fact whose workspace or meeting the person no longer has and lifts any other mark.
- `application/invariants.py` (`memory.check_invariant`, hourly): the facts a writer created after their person switched memory off, through the sweep role — `shosai_memory_written_while_off{home}`, which must stay 0.

## Monitors and tickets (step 11)

- `objectives.py`: the invariant monitor `memory_written_while_off` pages on the hourly check's gauge; the journey `leo_memory` shows recall's time and the admission's lag on memory's dashboard, with no promise. The rules and dashboards are generated from it (`pytest --update-rules`).
- `infrastructure/metrics.py`: `shosai_memory_extractions_total{source, outcome}` (a turn's or a meeting's model call), `shosai_memory_admission_lag_seconds` (from the turn's end, carried by `memory.admit_turn`, to its admission), `shosai_memory_candidates_total{source, answer}` (Remember, Don't remember, expired). The tickets on them are hand-written in `deploy/observability/prometheus/rules/tickets.yml`; each alert has its section in `docs/runbooks/alerts.md`.

## What the models read (step 1)

`infrastructure/extraction_prompts.py` (a turn's and a meeting's extraction) and `infrastructure/summary_prompts.py` (the summary and the box): English instructions with the output language stated in each, and their answer schemas — registered in the model-facing English test.
