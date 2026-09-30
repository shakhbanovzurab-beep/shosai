# Rewrite status

Every agent updates its row in the same commit as its work. Plan: [REWRITE_PLAN.md](REWRITE_PLAN.md).

Statuses: `todo` · `planned` (package plan written, approved) · `in progress` · `blocked` (say on what) · `done`.

| ID | Package | Depends on | Status | Package plan | Notes |
|---|---|---|---|---|---|
| D1 | API and WebSocket contract baseline | — | todo | — | |
| D2 | Visual baseline and parity harness | — | todo | — | |
| D3 | Data inventory and mapping | — | todo | — | |
| D4 | Feature map | — | todo | — | |
| F1 | Backend foundation | F3 | todo | — | |
| F2 | Frontend foundation | D2 | todo | — | |
| F3 | Local environment | — | todo | — | |
| F4 | Delivery to staging | F1, F2 | todo | — | Needs server, DNS and registry from the user |
| F5 | Observability | F1, F4 | todo | — | |
| S01 | Identity | F1, F2, F3, D1, D2 | todo | — | |
| S02 | Organizations | S01 | todo | — | New in v2 |
| S03 | Billing | S01 | todo | — | |
| S04 | Meetings | S01 | todo | — | |
| S05 | Realtime | S01 | todo | — | |
| S06 | Rooms | S01 | todo | — | |
| S07 | Knowledge and search | S01 | todo | — | |
| S08 | Storage | S01 | todo | — | |
| S09 | Agent (Leo) | S01 | todo | — | |
| S10 | MCP | S01 | todo | — | |
| S11 | Errands and scheduler | S01 | todo | — | |
| S12 | Connectors and calendar | S01 | todo | — | |
| S13 | Tracker | S01 | todo | — | |
| S14 | Analytics | S01 | todo | — | |
| S15 | Administration and support | S01 | todo | — | |
| S16 | Hub, downloads and remaining modules | S01, D4 | todo | — | Scope depends on D4 decisions |
| S17 | Public site | F2 | todo | — | |
| M1 | Data migration | all S, D3 | todo | — | Needs a copy of production data |
| M2 | Cutover | M1, F4, F5 | todo | — | |
