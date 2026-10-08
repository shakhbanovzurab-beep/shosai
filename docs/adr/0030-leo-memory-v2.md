# ADR 0030 — Memory v2: admitted facts with provenance and supersession, rendered as untrusted

- **Status:** accepted by the owner on 2026-10-08. Memory vectors live in pgvector in the home DB ([ADR 0033](0033-vectors-pgvector-for-memory-qdrant-for-knowledge-and-meetings.md), accepted).
- **Packages:** S09 (`memory`); S04 (memory port); S05 (user-context port).
- **Context documents:** [Leo architecture](../design/leo/ARCHITECTURE.md) §7.1, §7.2, §7.4; [Leo audit](../design/leo/AUDIT.md) M1–M5, A6; ARCHITECTURE.md fr-8, nfr-13, nfr-14.

## Context

The draft's memory (`memory_items`) is a single table of short texts with a 384-dimensional embedding, an importance, a confirmation count and decay. Its principles are good:

- pure domain functions;
- hard prompt caps;
- a soft-forget then purge lifecycle;
- an off switch that keeps the data;
- the graph-vs-memory boundary.

Its mechanics fail:

| # | Failure |
|---|---|
| M1 | The meeting pipeline and nightly consolidation ignore the off switch and `no_logs` |
| M2 | Consolidation reaches only the same 300 users every night |
| M3 | A merge keeps the longer text, not the newer, and every recall resets decay |
| M4 | No provenance and no embedding-model column; recall uses only the last message |
| M5 | Capture is decided by a 16-language regex and word lists, and raw user messages are stored |
| A6 | Memory is injected unwrapped as "your own knowledge", including third-party meeting speech |

## Decision

1. **`memory_facts`** in the home DB has these columns:
   - kind (preference · fact · relationship · goal · procedure) and statement, in the user's language, as user data;
   - `subject_refs` to context-graph entities;
   - provenance (`source_kind`, `source_ref`);
   - `confidence`, `sensitivity`;
   - `valid_from`, `valid_to`, `superseded_by`;
   - `embedding` with `embedding_model`;
   - `status` (candidate · active · forgotten), `pinned`.
2. **Admission, in the background after a turn:**
   1. a cheap model extracts at most 3 candidate statements from the **user's own messages** only;
   2. `decide(memory.admit)` with the 5 nearest neighbours judges kind, durability, sensitivity and update-of-neighbour;
   3. an update **supersedes** the old fact (newer wins, history kept);
   4. sensitive facts and the middle band become `candidate`, shown to the user to accept, and unused until accepted.
3. **Switches on every writer.** `memory_enabled=false` and `no_logs` stop extraction, the meeting memory port, consolidation and recall. An isolation test exists per writer.
4. **Retrieval:**
   - one query embedding per turn (last user message + start of the previous answer), shared with knowledge search;
   - top-40 → ranked by similarity × recency × confidence → ≤ 12 facts and ≤ 600 tokens;
   - recall does not refresh decay; only use or confirmation does.
5. **Rendering.** Facts are always wrapped as untrusted user data with their source label (`memory`, `meeting:speech`). A fact never changes policy. Statements judged to be instructions about Leo's behaviour are routed to personalization (subordinate preferences) or rejected.
6. **Profile core.** Pinned facts, preferences and personalization form a small, stable block (≤ 600 tokens) placed before the cache breakpoint (ADR 0031).
7. **User controls:** cursor list, edit, pin, forget one or all, accept or reject candidates, source shown per fact, export (fr-8), deletion (nfr-13).
8. **Consolidation** runs on a cursor over all users with memory on, only when facts changed since the last pass.
9. **Cross-border.** Embedding and extraction go through the provider port and require the same consent as Leo itself (nfr-14).

## Alternatives considered

| Option | Why not |
|---|---|
| Keep regex capture of raw messages (draft) | M5: language-dependent, stores commands as "episodes", rejects explicit requests |
| Extract memory synchronously in the turn | adds a model call to the hot path (nfr-7); background extraction loses nothing |
| A knowledge-graph-only memory (facts as edges in the context graph) | the context graph holds commitments and decisions with a lifecycle; personal preferences and profile facts need user controls and decay that the graph does not model |
| Memory as part of the thread summary only | not shared across scopes and threads; no user controls; no provenance |

## Consequences

- Leo can answer "why do you think that" from provenance. Contradictions resolve to the newer fact.
- One more cheap model call and one Jev request per turn with candidate text, both in the background.
- The meeting pipeline (S04) writes through the memory port only, with the switches enforced there.
- Memory vectors are in pgvector next to their facts ([ADR 0033](0033-vectors-pgvector-for-memory-qdrant-for-knowledge-and-meetings.md)): supersession, forgetting and deletion act on the fact and its vector in one transaction.

## Revisit when

- Admission precision measured from user accept and reject actions stays below 70% → change extraction or thresholds.
- Facts per active user exceed 5 000 → revisit retrieval (pre-filter by kind and subject).
