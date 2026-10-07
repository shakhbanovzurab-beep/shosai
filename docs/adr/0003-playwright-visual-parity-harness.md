# ADR 0003 — Playwright in a pinned container for the visual parity harness

- **Status:** superseded by [ADR 0022](0022-new-web-design-replaces-draft-parity.md) on 2026-10-07; accepted 2026-10-01 with the D2 plan
- **Date:** 2026-10-01
- **Package:** D2 ([plan](../plan/packages/D2-visual-parity.md))

## Context

The rewrite must be invisible to users: the same screens, layouts, texts and flows as the draft (CLAUDE.md, "Rewrite from the draft"). Type checks, unit tests and the React doctor do not see visual regressions. The draft learned this in its own migration: a style lost under an unlayered class is valid TypeScript, a green doctor and a passing test.

D2 needs a tool that renders both frontends from the same recorded API data and compares screenshots per route and state, reproducibly on any machine and in CI. No such tool is in the technology stack (CLAUDE.md, ARCHITECTURE.md §18), so adding one is a decision.

## Decision

- **Tool.** Use **Playwright 1.63.0** (`@playwright/test`), the latest stable release on 2026-10-01, as a development dependency of a separate npm project in `parity/`.
- **Runtime.** Run it only inside the official image pinned by digest: `mcr.microsoft.com/playwright:v1.63.0-noble@sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27` (Chromium build 1243, Node 24.20). Screenshots are compared only between runs of the same image.
- **Comparison.** Use the built-in `toHaveScreenshot`: per-pixel threshold, pixel budget, expected / actual / diff images and the HTML report.
- **Serving.** Serve the frontend under test and its fonts through Playwright request interception, with the `/v1` API replayed strictly from fixtures and every other host blocked.
- **Browser.** Chromium only. The harness compares two builds of the same design, and one engine is enough to see the differences between them. Cross-engine rendering differences are not parity regressions, and every added engine multiplies the baseline.

Upgrading Playwright or the image is a deliberate change: the whole baseline is re-captured in the same commit and checked with a full `verify` run.

## Alternatives considered

| Option | Why not |
|---|---|
| The draft's scripts (`frontend/tools/visual`, `playwright-core` with a host Chromium) | Hand-written pixel diff, permissive mock that answers unknown paths with `[]`, a browser path tied to one machine, no report. The lessons are kept (markers, fixed clock, blocked trackers); the code is not. |
| Playwright on the host | Rendering depends on host fonts and libraries. The baseline would not reproduce in CI or on another machine. |
| A hosted visual review service (Chromatic, Percy, Argos) | Sends screenshots of the product, with seeded data, to a third party. It adds a vendor and a bill for something a container does locally. |
| Storybook stories with visual tests | Covers components, not routes with real data and flows; v2 has no Storybook; the draft would need stories written first. |
| Cypress | No built-in screenshot comparison and no native WebSocket interception; the Leo voice mode and the user-events socket need WebSocket replay. |

## Consequences

- One more npm project with its own lock file, and one container image of about 2 GB on development hosts and CI runners.
- Pixel results are bound to the pinned Chromium build. A Playwright upgrade means re-capturing the baseline.
- The baseline is large: about 390 MB per full capture. The owner decided to keep it in an S3 bucket, with a hash manifest in git (plan §5).
- v2 must keep what the harness relies on: the `/app/` base path, the persisted client-state keys, the `/v1` contract and the selectors used as markers (plan §3.8). These are needed for an invisible cutover anyway.
