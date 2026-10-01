# ADR 0007 — Usage tombstones are kept for the lifetime quota

- **Status:** accepted by the owner on 2026-10-01 (D3, decision U-10 in [DATA_MAPPING.md](../plan/DATA_MAPPING.md#10-decisions-for-the-user)).
- **Package:** D3; applied by S03 and S04.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §8.2, inv-3, inv-13; [DATA_MAPPING.md](../plan/DATA_MAPPING.md) risk E-2.

## Context

§8.2 lists `usage_events` among the monthly-partitioned tables whose retention drops old partitions.

In the draft, a `usage_events` row is a tombstone written when a meeting is deleted. It keeps the minutes, AI questions and tokens of that meeting. The Free quota counts lifetime minutes:

- minutes of live meetings;
- two lifetime counters on the account;
- the sum of the tombstones.

Dropping old tombstones would give deleted minutes back. Deleting meetings would then become a way around the quota.

## Decision

`usage_events` keeps its monthly partitions but is **exempt from partition-drop retention**. A tombstone lives as long as its account, and is deleted with the account by the deletion registry.

## Consequences

- The table grows by one row per deleted meeting. The rows are small, and the growth stays far below the other partitioned tables.
- §8.2 states the exemption.
- If the Free quota ever becomes a quota per period, retention may drop partitions older than the oldest period still counted.

## Revisit when

- The tariff model replaces lifetime quotas with periodic ones.
- The table's size becomes material for backups or restore time.
