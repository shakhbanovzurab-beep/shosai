# ADR 0022 — The new web design replaces visual parity with the draft

- **Status:** accepted by the owner on 2026-10-07.
- **Packages:** D2, F2, every slice with screens, S17.
- **Supersedes:** [ADR 0003](0003-playwright-visual-parity-harness.md), [ADR 0017](0017-parity-stand-ins-and-pending-regions.md), [ADR 0018](0018-draft-fonts-vendored-in-the-frontend.md).
- **Context documents:** [CLAUDE.md](../../.claude/CLAUDE.md) "Rewrite from the draft"; [ADR 0021](0021-public-site-on-nextjs-cabinet-on-vite.md); [contracts/README.md](../../contracts/README.md); [SEO strategy](../seo/STRATEGY.md) 18.12.

## Context

- The rewrite's goal was that a user notices no visual difference from the draft: the same screens, layouts, texts and flows. D2 built a screenshot baseline of the draft (846 states, 1 614 screenshots) and a harness that compares v2 against it; F2 vendored the draft's fonts and planned stand-ins so every slice could prove pixel parity.
- The owner decided on a rebrand instead of a faithful copy and committed a new web UI on 2026-10-07 (`f4f8430`). Its screens, layouts and texts differ from the draft by design. The brand name is not final.
- Shipped native clients still depend on the HTTP and WebSocket contract (nfr-12); that is independent of how the web looks.

## Decision

1. **The reference for the web is the new UI** in `frontend/`, not the draft. Visual parity with the draft is no longer a goal, a check or a definition of done for any package.
2. **What still comes from the draft:** behaviour, business rules, flows that the new UI keeps, the data model lessons, and the API and WebSocket contract. The D1 contract baseline and its compatibility classes stay binding; `web` routes may change together with the new frontend, `native` and `external` routes may not.
3. **Superseded records:**
   - ADR 0003 — the parity harness is no longer a gate. `parity/` and the baseline in the bucket stay as a record of the draft's screens and states (useful for finding a flow or a state the new UI must still cover) until the owner removes them.
   - ADR 0017 — no stand-ins or pending regions; the `parity-compare` CI job is removed with the cabinet's move to Vite.
   - ADR 0018 — the draft's fonts are not vendored; the new UI's own fonts are used.
4. **The D2 inventory stays a coverage list.** A slice checks that every state of the draft's inventory it owns either exists in the new UI or is dropped with the owner's approval.

## Consequences

- No pixel gate guards the web against regressions. Visual regression checks for the new UI, if wanted, are a separate decision with their own baseline.
- F2's plan (written for parity) is replaced: the cabinet's foundation is the new UI moved to Vite (ADR 0021).
- SEO 18.12 is resolved: visible page rules (bylines, dates, breadcrumbs, trust pages) no longer wait for parity.
- Native clients are unaffected.

## Revisit when

- The owner wants a visual regression baseline of the new UI.
