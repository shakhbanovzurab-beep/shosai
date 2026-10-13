# ADR 0041 — Platform services re-planned from the product

- **Status:** accepted by the owner on 2026-10-13 (F6 plan decisions F6-D5 … F6-D8). Amends [ADR 0034](0034-platform-services-in-core.md) point 6 and the F6 plan's F6-D3.
- **Package:** F6, platform services; touches `studio`, `identity`, `billing`, `site`, M1 and M2.
- **Context documents:** [F1 audit](../plan/audits/F1-audit.md) §3.6 and OD-8; [F6 plan](../plan/packages/F6-platform-services.md); [SLICE_MAP.md](../plan/SLICE_MAP.md) §2.10, §4, §7.1, SM-12; [DATA_MAPPING.md](../plan/DATA_MAPPING.md) §5.23, §7.1; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §8.1, §13.2, inv-9, inv-13; [ADR 0022](0022-new-web-design-replaces-draft-parity.md).

## Context

The F6 plan of 2026-10-09 carried four parts from the draft rather than from the product: the draft's admin routes for costs and abuse, the draft's abuse guard with weights calibrated on the draft's traffic, the draft's email layout, and the draft's abuse tables and Valkey keys. The new cabinet has no cost, abuse or kill-switch screen; its AI models screen (`studio`) and its account card (`identity`) need the same data. The retention of AI cost rows was stated three ways: "never deleted" and "partitions > 24 months dropped" in §8.1, 24 months in the F6 plan.

## Decision

1. **No admin HTTP route in F6 (F6-D5).** Spend reports, one user's spend and the kill switch are application services. `studio`'s admin router serves them on the AI models screen, `identity`'s on the account card, each under SM-12's operator roles. Until `studio` ships, the CLI `shosai ai kill-switch {engage,release,status}` or `AI_KILL_SWITCH` engages the switch. The email-link routes (`/v1/unsubscribe`, `/email/{name}`) are public and built with email. `features/ai_control` is not built; F6 depends on F1 only.
2. **Rules instead of abuse scoring at launch (F6-D6).** Money: per-user ceilings by plan, Leo's background budget, platform and global ceilings, the kill switch. Load: at most 2 interactive streams or sessions in flight per user; **meetings and standard transcription (the `essential` class) count toward the cap but are never refused**. Size: input caps from settings. Attention: `ai.user_spend_exceeded` once per user and day above a threshold. No `abuse_states`, `abuse_events`, recompute job, cheap-model routing or review queue.
3. **The email layout comes from the cabinet's design system (F6-D7)** with email's technical rules (tables, inline styles, dark mode, RTL); the owner approves the rendered emails in the email step.
4. **Draft data (F6-D8).** `provider_costs` and `exchange_rates` are kept; `voice_sessions` and `translation_session` are folded into `provider_costs` rows in M1; `abuse_states`, `abuse_events` and `error_logs` are dropped; no draft Valkey key is carried — F6's `shosai ai rebuild-spend-counters` recomputes the counters from `provider_costs` at cutover and after a Valkey loss; the kill switch state is an M2 runbook step.
5. **AI cost rows are kept 5 years** (402-FZ), then their monthly partitions are dropped by core's upkeep (`keep_months = 60`). This one term replaces "never deleted" and "24 months" everywhere.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Keep `features/ai_control` with the draft's paths | No screen calls them (D1: `web` and `unused`); it would make F6 wait for `identity` |
| Keep the draft's scoring in shadow mode | Its weights fit the draft's traffic and prices; v2 would carry tables, a job and a state machine that decide nothing |
| Refuse every stream above the cap | A meeting or a standard transcription would stop on a user's third stream, against inv-13 |
| Keep cost rows forever | Five years is what the accounting law asks of these records; the partitions make the drop cheap and bounded |

## Consequences

- F6 has nine steps, all after F1; `identity`, `decisions` and `studio` depend on F6 as a whole.
- `studio`'s and `identity`'s admin steps include the screens' routes to F6's services.
- A slow automated user under every ceiling is not caught until scoring is designed on v2's data.
- M1 migrates five years of `provider_costs` and folds the session tables; DATA_MAPPING §5.23 and §7.1 follow this ADR.

## Revisit when

- The spend alert or the cost reports show abuse the ceilings do not stop: design scoring from v2's data.
- The accounting rules change the retention of cost records.
