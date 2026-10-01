# Rewrite status

Every agent updates its row in the same commit as its work. Plan: [REWRITE_PLAN.md](REWRITE_PLAN.md).

Statuses: `todo` · `planned` (package plan written, approved) · `in progress` · `blocked` (say on what) · `done`.

| ID | Package | Depends on | Status | Package plan | Notes |
|---|---|---|---|---|---|
| D1 | API and WebSocket contract baseline | — | todo | — | |
| D2 | Visual baseline and parity harness | — | todo | — | |
| D3 | Data inventory and mapping | — | todo | — | |
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
