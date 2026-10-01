# Rewrite status

Every agent updates its row in the same commit as its work. Plan: [REWRITE_PLAN.md](REWRITE_PLAN.md).

Statuses: `todo` · `planned` (package plan written, approved) · `in progress` · `blocked` (say on what) · `done`.

| ID | Package | Depends on | Status | Package plan | Notes |
|---|---|---|---|---|---|
| D1 | API and WebSocket contract baseline | — | done | — | [contracts/](../../contracts/README.md): draft OpenAPI and route table, 588 routes classified (34 native for macOS 1.4.5 and Windows 1.4.5, 74 external; Linux frozen, dead code not carried), 7 WebSocket endpoints catalogued, harness and CI job |
| D2 | Visual baseline and parity harness | — | in progress | [D2-visual-parity.md](packages/D2-visual-parity.md) | Steps 1–3b of 8 done: [inventory](../../parity/inventory/README.md) of 55 routes and ≈ 850 states; [recording stack](../../parity/recording/README.md) records 31 visits in ru and en; [harness](../../parity/README.md) with `baseline` / `verify` / `compare`, CI job; the shell, auth, account and billing group is complete: 145 states, 430 screenshots (31.7 MB) in the production bucket under `parity-baseline/`, reproduced with zero tolerance; [ADR 0003](../adr/0003-playwright-visual-parity-harness.md); next: step 4, meetings, calendar, context, knowledge, search |
| D3 | Data inventory and mapping | — | done | [DATA_MAPPING.md](DATA_MAPPING.md) | All 131 tables, 9 S3 prefixes, local disk, Redis and other stores mapped, aligned with D4; 33 risks with M1 verifications; the owner decided U-1…U-11: migrated accounts start in the RU home ([ADR 0004](../adr/0004-migrated-accounts-start-in-russian-home.md)), data without an owner in the EU home ([ADR 0005](../adr/0005-data-without-owner-in-eu-home.md)), the draft bucket becomes the RU bucket ([ADR 0006](../adr/0006-draft-bucket-becomes-russian-home-bucket.md)), usage tombstones kept ([ADR 0007](../adr/0007-usage-tombstones-kept-for-lifetime-quota.md)) |
| D4 | Feature map | — | done | [FEATURE_MAP.md](FEATURE_MAP.md) | Every draft module and frontend feature mapped; the owner decided FM-1…FM-5: hub, whiteboard, landing demo and help assistant kept; legacy notes merged into S07; OAuth outside Nango kept ([ADR 0002](../adr/0002-oauth-grants-outside-nango.md)); F6 added; routes D1 found unused dropped except four |
| F1 | Backend foundation | F3 | todo | — | |
| F2 | Frontend foundation | D2 | todo | — | |
| F3 | Local environment | — | done | — | `compose.dev.yaml`: two PostgreSQL 18 homes behind transaction-mode PgBouncer, Valkey, Redis cache, Qdrant, SeaweedFS; [development.md](../development.md); [ADR 0001](../adr/0001-local-environment.md) |
| F4 | Delivery to staging | F1, F2 | todo | — | Needs server, DNS and registry from the user |
| F5 | Observability | F1, F4 | todo | — | |
| F6 | Platform services | F1 | todo | — | Added by D4 (FM-4): AI provider port with cost rows, spend and abuse control; email; periodic-job registry |
| S01 | Identity | F1, F2, F3, F6, D1, D2 | todo | — | |
| S02 | Organizations | S01 | todo | — | New in v2 |
| S03 | Billing | S01 | todo | — | |
| S04 | Meetings | S01 | todo | — | |
| S05 | Realtime | S01 | todo | — | Broadcasts moved to S06 by D4 |
| S06 | Rooms | S01 | todo | — | Includes broadcasts, the room whiteboard and the room AI panel (D4) |
| S07 | Knowledge and search | S01 | todo | — | |
| S08 | Storage | S01 | todo | — | |
| S09 | Agent (Leo) | S01 | todo | — | |
| S10 | MCP | S01 | todo | — | |
| S11 | Errands | S01 | todo | — | Periodic jobs moved to F6 by D4 |
| S12 | Connectors and calendar | S01 | todo | — | |
| S13 | Tracker | S01 | todo | — | |
| S14 | Analytics | S01 | todo | — | |
| S15 | Administration and support | S01 | todo | — | |
| S16 | Hub, downloads and remaining modules | S01, D4 | todo | — | Scope set by D4: hubs, client downloads, top-bar ticker; the hub access model inside companies is settled in the slice plan |
| S17 | Public site | F1, F2, F6 | todo | — | Includes the landing demo and the help-centre assistant (D4) |
| M1 | Data migration | all S, D3 | todo | — | Needs a copy of production data |
| M2 | Cutover | M1, F4, F5 | todo | — | |
