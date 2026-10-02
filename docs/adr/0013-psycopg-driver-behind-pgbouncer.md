# ADR 0013 — psycopg 3 as the PostgreSQL driver behind PgBouncer

- **Status:** the driver (items 1, 2, 4) accepted by the owner on 2026-10-02 (F1 step 4, decision F1-D6); item 3, the TLS rule of the production gate, added by F1 step 4 and open to objection at its review.
- **Package:** F1, backend foundation; every slice reaches its home's database through it.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §3, §4.3, §13.4, §14 rule 2, §18.2, §19; [ADR 0001](0001-local-environment.md) (PgBouncer in transaction mode, `max_prepared_statements = 0`); [F1 plan](../plan/packages/F1-backend-foundation.md).

## Context

- §18.2 named asyncpg 0.31.0 as the driver. ADR 0001 later put each home's database behind PgBouncer in transaction mode with protocol-level prepared statements off, so that code that works locally works behind any provider's pooler. Without prepared statements asyncpg's statement cache must be off.
- The Russian home is 45 ms from the compute plane. §3 budgets 180 ms of database time per Russian request: four round trips (`BEGIN`, the tenancy scope of §7, one statement, `COMMIT`). §13.4 names this latency as what breaks first.
- With its cache off, asyncpg sends every statement in two round trips: Parse and Describe, then Bind and Execute. It needs the Describe answer to encode parameters in binary. It has no path that sends a parameterised statement in one round trip.
- Measured through a TCP proxy that counts the client's request turns, on SQLAlchemy 2.1.2 through the local PgBouncer:

  | Transaction | asyncpg 0.31.0, cache off | psycopg 3.3.6, `prepare_threshold=None` |
  |---|---|---|
  | scope + 1 statement | 6 round trips (270 ms to the RU home) | 4 (180 ms) |
  | scope + 3 statements | 10 (450 ms) | 6 (270 ms) |

- CPU per query through SQLAlchemy Core on loopback, median of 50: 20 rows — 0.39 ms with asyncpg, 0.38 ms with psycopg; 1000 rows — 4.15 ms and 4.75 ms.
- asyncpg's cache can stay on only if the pooler tracks protocol-level prepared statements (PgBouncer ≥ 1.21 with `max_prepared_statements > 0`). The providers' poolers are not chosen yet, and ADR 0001 rejected that dependency.

## Decision

1. **The application uses psycopg 3** (`psycopg[binary]`) through SQLAlchemy's `postgresql+psycopg` dialect, with `prepare_threshold=None`. Parse, Bind and Execute leave in one message: one round trip per statement, and no named statement is left on a server connection that another client reuses.
2. **Database addresses are standard libpq URLs** (`postgresql://…`); the code picks the driver. The query string may carry only TLS parameters (`sslmode`, `sslrootcert`, …). Connection behaviour — timeouts, application name, prepared statements, keepalives — is set by code and cannot be overridden by an address.
3. **In production every home's database is reached with `sslmode=verify-full`**; the production gate refuses any other address. The Russian home is across a national border and the public internet.
4. The test harness uses psycopg too, so the backend has one PostgreSQL driver. asyncpg is removed.

## Consequences

- A scoped read costs four round trips again, as §3 assumes; a test counts them through a proxy on every run.
- Row decoding of large result sets costs up to ≈ 15% more CPU than asyncpg; at the sizes the cabinet reads this is under a millisecond per query, against 45 ms per round trip saved for Russian users.
- psycopg reports no SQLSTATE for a refused connection: a wrong password and a lost link are told apart only by the driver's message, which the logs carry without the password.
- SQL in code uses SQLAlchemy constructs or `text()` with bound parameters; raw psycopg placeholders (`%s`) appear only in the test harness.
- §18.2 and §16.1 name psycopg; ADR 0001's consequence about asyncpg's statement cache is replaced by this ADR.

## Revisit when

- The providers' poolers are known and support protocol-level prepared statements: measure whether server-side preparation gains anything over one round trip per statement.
- asyncpg gains a one-round-trip path for unprepared statements.
- psycopg's decoding cost shows up in a profile of a real endpoint.
