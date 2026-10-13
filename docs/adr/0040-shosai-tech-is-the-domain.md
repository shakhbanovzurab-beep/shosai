# ADR 0040 — shosai.tech is Shosai's domain

- **Status:** accepted by the owner on 2026-10-13. Revisits [ADR 0037](0037-rebrand-whisperer-to-shosai.md) ("The owner acquires a Shosai domain").
- **Packages:** F4, F5, M2, `site`, every slice verified on the test domain.
- **Context documents:** [ADR 0037](0037-rebrand-whisperer-to-shosai.md); [ADR 0021](0021-public-site-on-nextjs-cabinet-on-vite.md); [contracts/README.md](../../contracts/README.md); [SEO strategy](../seo/STRATEGY.md).

## Context

- The owner registered **shosai.tech**; its A record points to the server that will run v2.
- `whisperer.one` runs the draft in production on a separate server. The shipped macOS and Windows clients call `https://whisperer.one/v1/...` and pin its certificate chain (contracts README).
- The plan named `one.whisperer.one` as the v2 test domain. No v2 deployment exists yet (F4 is open), so the test domain can change at no cost.

## Decision

1. **shosai.tech is Shosai's domain.** Site, cabinet (`/app`, `/admin`), API (`/v1`) and WebSocket gateway (`/v1/ws`) are served there. Every document, prompt and test names `shosai.tech`; `one.whisperer.one` is not used.
2. **Today shosai.tech is the test environment** (staging): its own databases, storage and secrets, the full production gate (F1 audit OD-7), not indexable. When production exists, production takes `shosai.tech` and the test environment moves to a subdomain; that move is decided with F4's production step.
3. **`whisperer.one` stays the draft's production server** and is not touched by v2 work. At cutover (M2) its API and WebSocket paths are pointed at v2, so the shipped native clients keep working without an update (nfr-12); it serves nothing else for v2.

## Consequences

- F4 deploys to `shosai.tech`; slices are checked there once F4 is done.
- The SEO strategy's canonical origin is `https://shosai.tech`; while it is the test environment, it answers `noindex` and is kept out of search.
- OAuth apps and webhooks of v2 are registered with `shosai.tech` callbacks. Migrated connections whose provider apps are registered with `whisperer.one` callbacks are re-registered or kept on the alias, decided in each owner's plan and in M1.
- Native clients are unaffected until cutover, and after it through the `whisperer.one` alias.

## Revisit when

- Production is ready → the test environment moves to a subdomain of `shosai.tech`.
- A native client release calls `shosai.tech` and the old releases are gone → `whisperer.one` can be retired.
