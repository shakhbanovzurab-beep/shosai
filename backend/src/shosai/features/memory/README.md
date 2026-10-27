# memory

What Leo knows about the person: their preferences, facts about them and their work, the people they deal with, their goals and how they work — each with its source, each visible, correctable and forgettable. Memory learns in the background from what the person says to Leo and from their meetings, puts the few facts that matter into a turn within a budget, and writes the overview the person reads in Settings › Memory.

- Plan: [docs/plan/slices/memory.md](../../../../../docs/plan/slices/memory.md). Decisions: MM-D1…MM-D8 in the plan and [ADR 0071](../../../../../docs/adr/0071-leo-memory-slice.md); the design is the [Leo architecture](../../../../../docs/design/leo/ARCHITECTURE.md) §7 with [ADR 0030](../../../../../docs/adr/0030-leo-memory-v2.md) and [ADR 0033](../../../../../docs/adr/0033-vectors-pgvector-for-memory-qdrant-for-knowledge-and-meetings.md).
- Public surface: none of its own. Memory binds the agent's `MEMORY_RECALL` and `PROFILE_FACTS` and reads the agent's `PERSON_WORDS` (`features/agent/contracts/memory.py`); it emits no event.

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

## What the models read (step 1)

`infrastructure/extraction_prompts.py` (a turn's and a meeting's extraction) and `infrastructure/summary_prompts.py` (the summary and the box): English instructions with the output language stated in each, and their answer schemas — registered in the model-facing English test.
