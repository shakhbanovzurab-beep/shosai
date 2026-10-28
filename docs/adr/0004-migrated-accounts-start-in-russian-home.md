# ADR 0004 — Accounts migrated from the draft start in the Russian home

- **Status:** accepted by the owner on 2026-10-01 (D3, decision U-1 in [DATA_MAPPING.md](../plan/DATA_MAPPING.md#10-decisions-for-the-user)).
- **Package:** D3; applied by M1 and S01.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.1, §6, nfr-4, fr-7; [DATA_MAPPING.md](../plan/DATA_MAPPING.md) rule R2.

## Context

§6 gives a personal account the home chosen by country at registration. Accounts of the draft were registered without that choice, and the draft stores no country of residence. The signals it does hold are weak or missing for many accounts:

- request geo snapshots in analytics events and satisfaction surveys;
- profile language, time zone and an optional phone number;
- quick sign-in with Yandex ID or VK ID;
- the currency and acquirer of payments.

All draft data lives in Russia today: managed PostgreSQL in St Petersburg and a Timeweb S3 bucket in `ru-1`. The EU home does not exist yet (CLAUDE.md, "Hosting constraints now").

## Decision

1. M1 assigns every migrated account to the **Russian home**: its rows, its objects and its Nango connections. Its directory entry carries the Russian home.
2. After cutover, accounts of people outside Russia move to the EU home by the account transfer (§6, fr-7). This happens once the EU home exists and the person confirms a country outside Russia in the product. The signals above only choose whom to ask.
3. Anonymised accounts stay in the Russian home with the financial rows that reference them.

## Consequences

- No data crosses a border at cutover, and the migration does not wait for the EU home.
- Until their transfer, the primary data of people outside Russia stays in Russia, as it does in the draft. This is a temporary gap against nfr-4 for them. It is added to the legal review in §22.
- S01 needs a flow that asks a migrated account for its country and starts the transfer.
- The transfer saga moves the account's Nango connections as well (S12); otherwise transferred users reconnect their connectors. *Amended on 2026-10-28 by [ADR 0075](0075-connections-on-own-oauth-core-without-nango.md): there is no Nango; connections are rows of the home and move with the table registry.*
- §6 states the rule for migrated accounts.

## Revisit when

- The EU home becomes available: plan the transfer wave and its pace.
- The legal review sets a deadline by which data of people outside Russia must leave the Russian home.
