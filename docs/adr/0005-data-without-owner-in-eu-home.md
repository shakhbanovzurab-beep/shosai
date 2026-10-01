# ADR 0005 — Data without an owning account lives in the EU home

- **Status:** accepted by the owner on 2026-10-01 (D3, decisions U-2 and U-8 in [DATA_MAPPING.md](../plan/DATA_MAPPING.md#10-decisions-for-the-user)).
- **Package:** D3; applied by M1 and by the slices that own these tables (S03, S07, S09, S10, S14, S15, S16).
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.1, §4.2, §6, §22; [DATA_MAPPING.md](../plan/DATA_MAPPING.md) rule R12.

## Context

§4.2 names the directory as the only content of the EU database that is not EU-home data. The draft also has tables with no owning account:

- prices and catalogs: `tariffs`, `promo_codes`, `payment_routes`, `exchange_rates`, `models_registry`, `model_defaults`;
- platform content: prompts and knowledge notes with an empty `user_id`, admin mailings (`broadcasts`), desktop builds (`app_builds`);
- operations: provider error logs (`error_logs`) and MCP client registrations (`mcp_registered_clients`).

Home tables reference some of them, for example `subscriptions.tariff_id` and `transactions.tariff_id`.

Telemetry without an account has no owner either: product events sent before registration, and client error reports sent anonymously.

The architecture does not say where any of this lives. The two options are one copy in one home, or the same rows in both homes.

## Decision

1. **Platform tables live in the EU home, next to the directory, as one copy with one writer.** The writers are the admin APIs and the platform's own jobs.
2. **Home tables reference platform rows by id without a foreign key.** A platform id is retired, never deleted. Reads may be cached as content; access rights are still never cached (§7).
3. **Telemetry without an account lives in the EU home.** This covers product events and client error reports.

## Consequences

- An admin edit is one write in one database: there are no cross-home writes and no sync job.
- Home tables lose foreign-key integrity to the catalog. The retire-only rule and an application check replace it, and M1 verifies that every migrated reference resolves.
- A request of a Russian-home user that reads platform data makes one extra read in the EU database, under 2 ms from the compute plane, and cacheable.
- **Promo codes:** a purchase commits in the buyer's home, while the promo code's use counter lives in the EU home. S03 applies the use through the outbox, with one use per transaction id, and keeps `used_count ≤ max_uses` in the EU home.
- **Anonymous telemetry** may hold IP addresses and device ids of people in Russia. This is accepted as a derived copy only if the legal review in §22 agrees; the item is added there.
- §4.2, §6, §22 and the diagram state the rule.

## Revisit when

- The legal review rules that anonymous telemetry of people in Russia must stay in Russia.
- A platform table needs a transaction together with home data beyond what the outbox gives.
