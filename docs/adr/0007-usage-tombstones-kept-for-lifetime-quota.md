# ADR 0007 — Usage tombstones are kept for the lifetime quota

- **Status:** accepted by the owner on 2026-10-01 (D3, decision U-10 in [DATA_MAPPING.md](../plan/DATA_MAPPING.md#10-decisions-for-the-user)); **amended on 2026-10-17** by [ADR 0054](0054-billing-plans-payments-trials-and-refunds.md) (BL-D3): the Free quota is monthly.
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

## Amendment (2026-10-17, ADR 0054, BL-D3)

The Free plan now gives 120 minutes a month; its quota is periodic, the case this ADR foresaw.

- A tombstone counts in the month its meeting happened, so deleting a meeting never gives its minutes back within that month.
- `usage_events` returns to ordinary partition-drop retention: partitions older than the current and the previous month (the month a late deletion may still fall into) are dropped by core's daily tick. M1 keeps the draft's tombstones until its E-2 check has run.
- Tombstones still go with their account through the deletion registry.
- The draft's lifetime counters (`no_logs_minutes_used`, `ai_minutes_used`) are not carried as quotas; migrated Free accounts start a fresh month at cutover.
