# D2 — Visual baseline and parity harness

Follow the common protocol in `docs/plan/prompts/README.md`.

## Goal

The rewrite must be invisible to users: the same screens, layouts, texts and flows. Build the instrument that proves it — screenshots of the draft and of v2, rendered from identical data, compared automatically.

## Inputs

- Draft frontend: `/root/whisperer/frontend/` — routes (`src/app/router/`), features, locales (16 languages), styles.
- Draft backend responses, to record fixtures.
- D1 output in `contracts/`, if it exists; otherwise derive the endpoints yourself.

## Work

1. Inventory every route and every significant UI state: empty, loading, populated, error, modal and drawer states, onboarding steps, paywalls.
2. Record API fixtures for those states as static JSON, from the draft backend running locally with seeded test data. Never use production data.
3. Build a harness with Playwright (latest stable, a new dev tool: record it in an ADR) that serves a frontend against the fixtures instead of a real backend, and screenshots every route and state.
4. Matrix: desktop and mobile viewports; light and dark themes if the draft has them; locales `ru` and `en` for every state, plus one screen in each remaining locale to catch layout breaks in long or right-to-left scripts (`ar`).
5. Run it on the draft and store the draft screenshots as the baseline in `parity/baseline/`.
6. Comparison mode: run the same matrix on v2 and report differences above a small threshold, per route and state, with diff images.

## Output

- `parity/`: harness, fixtures, route and state inventory, baseline screenshots, `parity/README.md` explaining how a slice runs it for its own routes.

## Definition of done

- Every draft route is in the inventory.
- The baseline is captured and reproducible: two runs on the draft give no differences.
- A slice can run the comparison for a subset of routes with one command.
- Tell the user if the baseline size is large enough to need Git LFS or storage outside git; do not decide that alone.
