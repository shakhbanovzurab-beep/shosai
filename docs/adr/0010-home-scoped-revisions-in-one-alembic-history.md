# ADR 0010 — Home-scoped revisions in one Alembic history

- **Status:** accepted by the owner on 2026-10-01 (F1 planning, decision F1-D3).
- **Package:** F1, backend foundation; applied by S01 (directory), the slices that own platform tables (ADR 0005), S14 (telemetry without an account) and M1.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.1, §6, §17; [ADR 0005](0005-data-without-owner-in-eu-home.md); [F1 plan](../plan/packages/F1-backend-foundation.md).

## Context

The same migrations are applied to both homes (F1 prompt, item 8). Some tables live only in the EU home: the directory (§6), the platform tables and the telemetry without an account (ADR 0005). Nothing says whether the Russian home has empty copies of them.

An empty copy turns a routing mistake into a silent wrong answer: code that reads tariffs from the Russian home by mistake gets "no tariffs" instead of an error.

## Decision

1. **One linear Alembic history for both homes.** `alembic_version` holds the same revision in both.
2. **A revision runs in every home unless it declares `applies_to`**, for example `applies_to = (Home.EU,)`. In other homes it is skipped but stamped, so both homes stay on the same revision.
3. **A revision is either for every home or scoped; it never mixes.** A change that needs both is split into two revisions.
4. **EU-only tables do not exist in the Russian home:** the directory tables, the platform tables of ADR 0005, the telemetry without an account. A read routed to the wrong home fails with "relation does not exist".
5. **Code names the home of platform and directory data explicitly** (`Home.EU`); it never takes it from the request's home.
6. **A process refuses to start unless every home is at the head revision** (draft specification 035), and the release applies migrations to both homes before any process starts (§17).

## Consequences

- The revision template carries `applies_to`; a test checks that scoped tables are absent from the other home.
- Downgrades respect the scope in the same way.
- M1 copies platform tables into the EU home only.

## Revisit when

- A third home is added: `applies_to` takes it as is.
- A home needs a platform table inside its own transaction beyond what the outbox gives (the same trigger as ADR 0005).
