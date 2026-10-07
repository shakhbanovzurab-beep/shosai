# F2 — Frontend foundation (cabinet on Vite)

Follow the common protocol in `docs/plan/prompts/README.md`. Load the skills `vercel-react-best-practices`, `vercel-composition-patterns`, `vercel-react-view-transitions` and `web-design-guidelines` before reading the code or designing anything; load `react-doctor` before running the gate.

**This package is multi-session.** Work in the session mode described in `docs/plan/prompts/README.md`. The package plan is `docs/plan/packages/F2-frontend-foundation.md`; the plan of 2026-10-02 there was written for visual parity with the draft and is superseded ([ADR 0022](../../adr/0022-new-web-design-replaces-draft-parity.md)). The first session writes a new plan.

## Goal

The cabinet in `frontend/` — the new web UI committed on 2026-10-07 on Next.js — runs as a **Vite single-page app** ([ADR 0021](../../adr/0021-public-site-on-nextjs-cabinet-on-vite.md)), looks and behaves exactly as it does now, and is the project every slice builds its screens into. After this package the frontend CI job runs and is green.

## Read first

- ADR 0021 and ADR 0022; CLAUDE.md "Frontend" and "Checks"; target architecture §4.2, §5, §18.2.
- `frontend/` as committed in `f4f8430`: `src/app/` (routes, layouts, metadata), `src/features/`, `src/i18n/`, `src/proxy.ts`, `package.json`, `doctor.config.json`, `src/scripts/` (architecture and i18n checks).
- `contracts/README.md` (D1): which routes are `web` and may change with the new frontend.

## Work

1. Vite project, latest stable, with React 19.3 and TypeScript; the libraries of §18.2 that the cabinet needs (React Router, TanStack Query, Zustand, Tailwind); `use-intl` for translations. Versions pinned in `package-lock.json`; `.nvmrc` stays 26.10.0.
2. Routing: every page and layout of `src/app/` becomes a React Router route with lazy loading, under the same paths and query parameters. `next/link`, `next/navigation`, `next/dynamic`, `next/font` and `next-themes` are replaced.
3. Translations: `next-intl` and `next-intl/server` → `use-intl`; locale detection moves from `src/proxy.ts` to the client; the 16 message catalogues and their keys stay as they are.
4. Page metadata: `metadata` and `generateMetadata` → `<title>` and `<meta>` rendered by the page; the cabinet sends `noindex`.
5. The sample backend (`src/app/api/`, `src/server/`, `features/*/server/`) is removed. The data layer is a client generated from the backend's OpenAPI contract with the error envelope of ADR 0008; how screens get data before their slice publishes endpoints is a decision of the plan (for example mocks in development and tests, removed slice by slice).
6. Public pages (`sitemap.ts`, `robots.ts`, Open Graph images, `/s/[token]`) leave `frontend/`; they belong to the public site (S17).
7. npm scripts required by CLAUDE.md "CI": `typecheck`, `test` (single run), `build`, `doctor`. The CI frontend job and the repository checks fit the new project; the `parity-compare` job is removed (ADR 0022).
8. Every file within the 200-line limit; the architecture check of `src/scripts/` runs in `npm test`.

## Definition of done

- Every screen of the cabinet renders as it did on Next.js, in both themes, on desktop and mobile widths, in the 16 languages.
- No Next.js dependency in `frontend/`; no API inside `frontend/`.
- `npm run doctor -- --score` prints 100; `typecheck`, `test` and `build` pass.
- CI frontend job is green after push.
