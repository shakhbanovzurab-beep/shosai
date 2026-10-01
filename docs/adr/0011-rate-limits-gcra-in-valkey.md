# ADR 0011 — Request rate limits: GCRA in Valkey through redis-py

- **Status:** accepted by the owner on 2026-10-01 (F1 planning, decision F1-D4).
- **Package:** F1, backend foundation; the limits themselves are declared by the slices that own the routes.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.2, §4.3, §13.2, §18.2; [CLAUDE.md](../../.claude/CLAUDE.md) "Engineering principles" (async first); draft specifications 010 and 020; [F1 plan](../plan/packages/F1-backend-foundation.md).

## Context

- The draft's specifications require limits keyed by the real client IP or the authenticated user, enforced across processes: sign-in 5 per minute per IP, AI routes 30 per minute per user, public build download 30 per minute per IP. Specification 020 found that limits kept in process memory multiply by the number of processes.
- §18.2 named slowapi 0.1.10. slowapi works only with the synchronous storage of the `limits` library: with Redis every limited request blocks the event loop for one round trip to Valkey; with memory storage the limit multiplies by the number of processes.
- The asynchronous API of `limits` needs `coredis` or `valkey-py`, a second Redis client next to `redis-py`, which the project already has for TaskIQ.

## Decision

1. **Own limiter on `redis-py`:** the generic cell rate algorithm (GCRA) in one Lua script, one atomic round trip per check. State is one key per limit and subject, with a TTL equal to the time to refill; Valkey runs with `noeviction`, so keys leave only by TTL.
2. **A slice declares a limit on a route** through a FastAPI dependency: name, rate, burst and subject — the client IP (from the trusted proxy) or the authenticated user.
3. **Over the limit:** 429 with the error envelope (`rate_limited`, ADR 0008) and `Retry-After`.
4. **Valkey unavailable or slower than 50 ms:** the request is allowed (fail open, as in specification 020), counted in a metric and logged as a warning. A limit is protection, not an invariant; money and rights never depend on it.
5. **§18.2 no longer lists slowapi.**

## Consequences

- About a hundred lines of own code, covered by property tests (Hypothesis) and tests against Valkey; no new dependency.
- WebSocket routes are not limited by this mechanism (as in specification 010); the WS gateway has its own slot limits (§4.3).
- Per-IP limits rely on the trusted-proxy configuration; production refuses to start without it.

## Revisit when

- A maintained asynchronous limiter on `redis-py` appears and covers the same needs.
- A limit is needed that GCRA cannot express, for example a quota over days; that belongs to billing, not to this limiter.
