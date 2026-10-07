# ADR 0017 — Stand-ins and pending regions for visual parity during the rewrite

- **Status:** superseded by [ADR 0022](0022-new-web-design-replaces-draft-parity.md) on 2026-10-07; accepted by the owner on 2026-10-02 (F2 planning, decisions F2-D1 and F2-D6).
- **Package:** F2, frontend foundation; applied by every slice until the last one lands.
- **Context documents:** [ADR 0003](0003-playwright-visual-parity-harness.md); [parity/README.md](../../parity/README.md); [D2 plan](../plan/packages/D2-visual-parity.md) §3.8; [F2 plan](../plan/packages/F2-frontend-foundation.md) §3.11; [REWRITE_PLAN.md](../plan/REWRITE_PLAN.md) §4.

## Context

- The D2 baseline is a screenshot of the whole page. Every state inside the shell also shows pixels of other slices: the 28 menu entries of the draft's 18 features, the Leo button (S09), and the page under the shell — `/analytics` (S14) on `shell.user`, `/download` (S16) on `shell.admin`.
- Slices are built in any order and in parallel. F2 builds the shell before any slice exists, and its definition of done asks for the shell to match the draft.
- So without a rule, F2 cannot prove the shell, and no slice can pass its own comparison until every other slice exists.
- Masks in the harness are written per state with a reason and are part of the baseline image. Adding masks to existing states would need new baseline images for every combination of missing slices.

## Decision

1. **Stand-ins.** `frontend/parity-build/` is a test-only composition. For every draft feature that no production slice has registered, it adds the feature's menu entries and routes, taken as data from the draft's manifests at the pinned commit. `npm run build:parity` builds the production registry plus the stand-ins into `frontend/dist-parity/`, which `parity.config.json` names as the v2 target. It is never deployed.
2. **Pending regions.** An element marked `data-parity-pending="<slice>"` stands for pixels of a slice that does not exist yet: a stand-in's route marks the content area, a stand-in widget marks the box where the draft draws it (the Leo button). In `compare`, after the page settles, the harness takes the visible pending boxes, paints them in the mask colour on a copy of the expected image, and masks the same boxes in the actual screenshot. `baseline` and `verify` render the draft and never see the attribute.
3. **Honest boxes.** A draft widget larger than its pending box leaves unmasked pixels and fails the state, so a box is at least as large as what it stands for in every cell.
4. **Removal.** A slice deletes its stand-in in the commit that registers it, so its own pixels are compared unmasked from then on. Tests fail when a registered slice still has a stand-in, and when production and stand-in menus together differ from the draft's menu. When the last stand-in is gone, the parity build equals the production build and `parity.config.json` points back to `frontend/dist`.
5. **Rule change.** Pending boxes are masked without a per-state reason. Every other mask still needs a written reason, and the global tolerance is never raised.
6. **CI.** A `parity-compare` job compares the state ids listed in `parity/compare.json` on every push. Each slice adds its own ids when it is done. The job reads the baseline images with a read-only key limited to `parity-baseline/`, from the repository secrets `PARITY_S3_ENDPOINT`, `PARITY_S3_REGION`, `PARITY_S3_BUCKET`, `PARITY_S3_ACCESS_KEY_ID` and `PARITY_S3_SECRET_ACCESS_KEY`. Until the secrets exist, the job reports that it was skipped and passes; it never fails the build for missing secrets.

## Consequences

- F2 proves the shell, including the full menu, while slices are absent; every slice compares its states as soon as it exists.
- Pixels under pending boxes are not compared until their slice lands. The last slices therefore close the comparison of the whole page.
- About 200 lines of test code in the frontend and about 100 in the harness, all removed or inert when the rewrite ends.
- While the secrets are missing, visual comparison is a local check that each step reports; CI does not guard it.

## Revisit when

- The last slice is registered: delete `frontend/parity-build/` and the pending logic.
- A slice needs a pending box that is not a rectangle the size of a widget; then it states its case to the owner.
