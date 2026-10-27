# ADR 0033 — pgvector for Leo's memory, Qdrant for knowledge and meetings

- **Status:** accepted by the owner on 2026-10-08. Closes the "role of `pgvector`" item of [CLAUDE.md](../../.claude/CLAUDE.md) "Undecided" and question Q-1 of the [Leo architecture](../design/leo/ARCHITECTURE.md) §17. Amended on 2026-10-27 by [ADR 0071](0071-leo-memory-slice.md): memory recall is an exact scan of the person's own current facts through a b-tree on the person, not HNSW (a global graph filtered to one person loses results); vectors are `halfvec(1024)`; the revisit rule below stands.
- **Packages:** S09 (`memory`), S04 (meeting windows), S07 (knowledge).
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §3, §4.2, §7, §8.1, §18.2; [ADR 0030](0030-leo-memory-v2.md).

## Context

The target architecture names two vector stores and does not say which vectors live in which:

- **Qdrant** (§4.2): the vector index for knowledge chunks and per-minute meeting windows. Its payload carries tenant and access, and every hit is re-checked in PostgreSQL.
- **pgvector** (§18.2): "vectors in PostgreSQL". The test infrastructure requires the extension.

Leo's long-term memory (ADR 0030) needs vectors too. Its properties differ from knowledge and meetings:

| Property | Memory facts | Knowledge and meeting windows |
|---|---|---|
| Owner and access | one user | a user, a company, grantees |
| Volume | small: up to thousands of rows per user | large: ≈ 0.78 M meeting windows per day (§3), knowledge corpora |
| Writes | each tied to a fact change: supersession, forgetting, deletion | bulk indexing by cursor; derived and rebuildable |
| Residency | primary data of the user, in the user's home | derived copies accepted in the EU (§6) |

## Decision

1. **Leo's memory vectors live in pgvector**, in the `memory_facts` table of the user's home database. The embedding sits next to its fact and its `embedding_model` column.
2. **Knowledge chunks and meeting windows live in Qdrant**, as §4.2 already states, with a tenant and access filter and a PostgreSQL re-check of every hit (§7, inv-10, inv-14).
3. **No other vectors are added without a new decision.**

## Consequences

- **One transaction for a fact and its vector.** Supersession, forgetting, account deletion and the memory switch act on the fact and its vector at once. There is no derived copy to purge or rebuild.
- **Residency.** Russian users' memory, vectors included, stays in the Russian home. It is not copied to the EU index.
- **Load.** Memory recall is one vector query over one user's rows. This is a small, indexed scan (HNSW), well inside the home's per-request budget.
- **Qdrant is unchanged**, and a Qdrant outage does not affect memory recall (Leo architecture §11.1).
- §18.2 states pgvector's purpose as "vectors of Leo's memory in the home database".

## Revisit when

- Memory facts per active user exceed 5 000, or memory recall exceeds 20 ms p95 in a home.
- Another feature needs vectors: it gets its own decision, by the same criteria.
