# ADR 0031 — Budgeted, cache-stable context with result digests and background compaction

- **Status:** proposed on 2026-10-08; awaits the owner.
- **Packages:** S09 (`agent`, `memory`).
- **Context documents:** [Leo architecture](../design/leo/ARCHITECTURE.md) §7.3, §7.4, §12; [Leo audit](../design/leo/AUDIT.md) T1, T2, C6, A4, A5; ARCHITECTURE.md nfr-7.

## Context

The draft caps history at 40 messages, counted as messages, not tokens. Raw tool results are kept, some of them tens of KB. Context files are injected in full on every turn with no total cap, and attachments can reach 256 K characters. Nothing is summarised.

A minute-level timestamp and per-turn memory sit near the top of the prompt, so the history prefix can never be cached. Tool schemas add 20–25 K tokens per round. The truncation flag (`finish_reason=length`) is ignored. External text is wrapped by a marker that can be escaped, and many channels are not wrapped at all.

## Decision

1. **Eight segments with hard caps**, ordered from static to volatile:

   | # | Segment | Cap (tokens) |
   |---|---|---|
   | 1 | Platform policy | 1 500 |
   | 2 | Tool schemas | 4 000 |
   | 3 | Skill | 1 500 |
   | 4 | Profile core | 600 |
   | — | **cache breakpoint** | |
   | 5 | Thread summary | 1 000 |
   | 6 | Recent messages | 5 000 |
   | 7 | Volatile context (time, surface, memory, mentions, attachment digests, knowledge) | 2 500 |
   | 8 | User message | 4 000 |

   This totals about 20 K at the caps and 10–12 K in a typical turn. Caps are per model tier and configuration.
2. **Tool results.** A result over its budget is stored in full in the thread for 30 days. The context gets a digest (counts, first items, `truncated: true`, `result_ref`), and `read_result(ref, cursor)` pages through the rest.
3. **Compaction** runs in the background after a turn, when the recent segment passes 70% of its cap. A cheap model folds the oldest turns into the thread summary. The hot path never waits; if compaction lags, the oldest turns are dropped.
4. **Attachments** are uploaded and referenced. Their digests stay available on later turns, and the full text goes through `read_result`.
5. **Cache stability.** Segments 1–4 are byte-identical across turns unless their inputs change, and a test asserts this. An explicit cache breakpoint is set where the provider supports it.
6. **Truncation honesty.** On `finish_reason=length`, the message is marked truncated, and truncated tool calls are rejected.
7. **Untrusted wrapper v2.** Untrusted text gets:
   - a per-run random boundary;
   - escaping of boundary-like sequences;
   - provenance labels from a closed set, never attacker text;
   - one format everywhere.

   Each run carries a taint level (`none` · `external` · `suspicious`) that drives egress, card warnings, voice approval and memory admission.

## Alternatives considered

| Option | Why not |
|---|---|
| Rely on the model's long context window | cost and latency grow linearly with every round; quality degrades on long, noisy contexts; caching breaks on any volatile prefix |
| Summarise synchronously before each turn | adds a model call to the hot path (nfr-7) |
| Truncate only by message count (draft) | T2: one tool result can be larger than the rest of the context |
| Retrieval over the whole thread instead of a summary | misses implicit context and pronouns; adds an index per thread; a rolling summary plus recent turns covers the common case |

## Consequences

- **Typical input** for a first round falls to about 10–12 K tokens; the draft sent about 30 K before history.
- **Per-turn cost** at the design point falls by about 4× on input tokens, an estimate in the architecture §12.
- **A cheap-model call per compaction**, about once every few turns per active thread, in the background.
- **New tests:** segment caps, prefix stability, wrapper escaping, truncation handling.

## Revisit when

- The default tier changes to a model whose cached input price makes context size immaterial and whose quality holds on long contexts (measured on the trajectory suite).
- Compaction lag drops turns in more than 1% of runs.
