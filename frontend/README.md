# Shosai cabinet

The signed-in web application of Shosai: the user panel (`/app/*`) and the admin panel (`/admin/*`). A Vite
single-page app and installable PWA; the public site lives in `site/` ([ADR 0021](../docs/adr/0021-public-site-on-nextjs-cabinet-on-vite.md)).
The backend is the FastAPI API in `backend/`; the cabinet owns no API.

## Stack

React 19.3 with React Compiler, TypeScript, Vite, React Router, TanStack Query, Zustand, `use-intl` (16
languages), Tailwind CSS v4 and shadcn/ui, MSW for development mocks, Vitest, Biome. Versions are pinned in
`package-lock.json`; `.npmrc` takes only releases at least 7 days old.

## Run locally

Node.js from `.nvmrc`.

```bash
npm ci
npm run dev        # http://localhost:3000/app/ — the sample API answered by mocks in the browser
npm run dev:api    # the same, calling the local backend (BACKEND_URL, default http://localhost:8000) instead
```

The admin panel opens at `/admin/dashboard`. Mocks never reach a production build.

## Scripts

| Script | What it does |
|---|---|
| `typecheck` | Generates the message types, then `tsc --noEmit` |
| `test` | Vitest: unit tests, the architecture check, the i18n check, OpenAPI types in sync |
| `build` | `vite build` into `dist/`, then the bundle check (no mocks, no source maps, CSP hashes present) |
| `doctor` | react-doctor; the CI gate is `npm run doctor -- --score` = 100 |
| `api:types` | Generates `src/lib/api/generated/schema.d.ts` from `../backend/openapi.json` |
| `i18n:check`, `i18n:rtl-smoke` | The i18n check alone; the right-to-left smoke run against a running cabinet |
| `check`, `check:fix` | Biome lint and format |

## Deploying

`dist/` is static: the edge serves it under `/app/` and answers `index.html` for the cabinet's paths
(`tooling/cabinet-paths.ts`), with `X-Robots-Tag: noindex`, long-lived caching of `/app/assets/*` and a CSP that
allows the inline boot scripts by the hashes in `dist/csp-hashes.json`.

## Documentation

- [docs/architecture.md](docs/architecture.md) — structure, slices, routing, data, the checks that enforce them
- [docs/i18n.md](docs/i18n.md) and [src/i18n/GLOSSARY.md](src/i18n/GLOSSARY.md) — languages and wording
- `docs/<slice>-api.md` — the sample API each slice calls until its backend endpoints exist
