# ADR 0024 — Leo's conversations live in the home database; Valkey keeps only in-flight runs

- **Status:** proposed on 2026-10-08; awaits the owner. **Amends** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §8.1 "Leo state" (see the architecture §16).
- **Packages:** S09 (`agent`).
- **Context documents:** [Leo architecture](../design/leo/ARCHITECTURE.md) §5, §10; [Leo audit](../design/leo/AUDIT.md) C1, C2, C8; ARCHITECTURE.md §6, §8.1, §14 rule 1.

## Context

In the draft, a conversation exists in two places:

- **The browser.** Each browser keeps the visible history in localStorage and re-sends it with each turn.
- **The server.** It keeps a LangGraph checkpoint in Redis, with a TTL of 24 h, the frozen system prompt and the last 40 messages.

§8.1 records the second place as the design: "checkpoints in Redis, TTL 24 h … loss restarts the dialogue". The consequences, all found in the audit:

- **No continuity.** There is no conversation list. A conversation does not follow the user across devices. Two tabs overwrite each other (C1).
- **Forged history.** After the TTL the server re-seeds the thread from client-sent history, so a forged assistant turn enters the context (C1).
- **Lost turns.** Two concurrent turns on one thread start from the same checkpoint, and one turn's messages are lost (C2).
- **Bloat and leftovers.** Every superstep writes a full snapshot, including the system prompt. Threads are never deleted with the account (C8).
- **Residency.** The whole text of Russian users' conversations sits in the EU store for 24 h (§6 accepts this only as a derived copy).

The new cabinet design needs threads per scope (personal, workspace, hub) and continuity across devices.

## Decision

1. **Authoritative in the home DB:**
   - `agent_threads`: id, user, org, scope kind and id, title, summary, summary cursor, timestamps;
   - `agent_messages`: monthly partitions, UUIDv7; role, content, tool digests, `result_ref` payloads (kept 30 days), run id.

   Russian users' conversations stay in Russia.
2. **Commit order.** A turn commits the user message and the `agent_runs` row in one transaction before streaming. It commits the assistant message and usage in one transaction at the end (§14 rule 1). The client never sends history.
3. **Valkey keeps only in-flight state:**
   - the thread lease (one active run per thread; renewed every 10 s; lease 30 s);
   - the LangGraph checkpoint of an **active or paused** run, deleted when the run completes;
   - the run's event log for stream resume (TTL 1 h).

   Every TTL is ≤ 24 h, which keeps the §6 exception.
4. **Checkpoint content is references.** It holds message ids and segment hashes, not the system prompt or the history. Writes deduplicate by channel version.
5. **A busy thread returns `409 thread_busy`**, unless the turn carries `supersede: true` ("stop and send").
6. **Deletion.** Threads, messages, checkpoints and event logs are in the account deletion registry (§14 rule 7).

## Alternatives considered

| Option | Why not |
|---|---|
| Keep §8.1 as is (Redis only, client history) | C1, C2; no conversation list; forged history; residency of full conversations in the EU |
| LangGraph's PostgreSQL checkpointer as the conversation store | stores graph internals per superstep; schema owned by a library; one connection pattern (session-bound) at odds with PgBouncer transaction mode ([ADR 0013](0013-psycopg-driver-behind-pgbouncer.md)); messages are a product entity, not a framework snapshot |
| Messages in Valkey with a longer TTL | Valkey is not the source of truth for user data (§8.2, §6); RPO of AOF; residency |
| One row per thread with a JSON array of messages | unbounded row growth, write amplification per turn, no cursor pagination (§10 contract rules) |

## Consequences

- Continuity, history pagination, search over one's own conversations later, and correct deletion.
- Valkey memory for Leo drops from about 2.5 GB (≈ 50 000 threads × 50 KB for 24 h) to tens of MB of active runs.
- **Volume.** About 150 000 rows/day at the design point, ≈ 30 GB/year after the payload trim, split between homes.
- **Latency.** Two home-DB transactions per turn: ≈ 8 ms for EU users and ≈ 90–135 ms for Russian users (accepted by §20).
- The new UI's client-held history (`chat-store.ts`) is removed. Its web routes change as ADR 0022 allows.
- At cutover, draft checkpoints are dropped (DATA_MAPPING U-5): a pending confirmation is asked again.

## Revisit when

- Thread rows exceed 5 GB/month in one home, or history reads exceed 10% of that home's DB time → move tool payloads to object storage.
- Compute moves next to the Russian DB (§19), which would remove the Russian latency trade-off.
