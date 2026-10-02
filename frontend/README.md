# Whisperer frontend

The web cabinet: a Vite single-page app served under `/app/`, built feature-first. Every feature slice builds its screens into it. [F2](../docs/plan/packages/F2-frontend-foundation.md) builds the foundation step by step; this README grows with it, and its last step adds the guide for slices (manifest, namespaces, stand-in removal, compare list).

## Commands

Node.js comes from [`.nvmrc`](.nvmrc); npm installs exactly the versions in `package-lock.json`. [`.npmrc`](.npmrc) pins every new dependency to an exact version and refuses versions published less than 7 days ago (`min-release-age`), so a freshly published malicious release cannot get in. An urgent fix that cannot wait passes `--min-release-age=0` to that one `npm install`, and the commit says why.

| Command | What it does |
|---|---|
| `npm ci` | Installs the locked dependencies |
| `npm run dev` | Dev server on `http://127.0.0.1:5173/app/` |
| `npm run typecheck` | `tsc -b` over the app (`tsconfig.app.json`), the tests (`tsconfig.test.json`) and the Vite and Vitest configs (`tsconfig.node.json`) |
| `npm test` | Vitest, one run: unit, component and architecture tests in `tests/` |
| `npm run build` | Production bundle in `dist/` (base `/app/`); the parity harness serves it |
| `npm run doctor -- --score` | react-doctor; the gate is `100` |

CI (`.github/workflows/ci.yml`, job `frontend`) runs `npm ci`, `typecheck`, `test`, `build` and `doctor -- --score` on every push.

### react-doctor and the network

react-doctor computes the score on its vendor's service, not locally ([ADR 0020](../docs/adr/0020-react-doctor-score-from-the-vendor-service.md)). Every run sends the findings (rule, file path, line, message), the repository name and the commit to `react.doctor`, and the name and version of every dependency to Socket.dev; without network there is no score. The `doctor` script sets `REACT_DOCTOR_NO_TELEMETRY=1`, which keeps its traces, metrics and crash reports at home. Do not pass `--no-score`: it removes the score the gate reads.

## Layout

| Path | Holds |
|---|---|
| `src/entrypoints/` | The entry module: mounts the app into `#root` |
| `src/composition/` | The composition root: registry of slices, router assembly, providers |
| `src/shell/` | The app frame: layout, navigation, top bar, fallbacks |
| `src/features/<slice>/` | One slice; its public surface is `feature.ts` (the manifest) and `contracts.ts` |
| `src/core/` | What the shell and every slice share: API client, session, i18n, theme, styles, UI kit |
| `parity-build/` | A test-only composition for the parity harness; never deployed |
| `tests/` | Vitest suites |

Directories appear with the step of the plan that fills them.

## Boundaries

`tests/architecture/` enforces the rules of the plan (§3.2) on every `npm test`, with zero allowed violations. It reads `src/` and `parity-build/` with the oxc parser that Vite exports (`parseSync`); each rule has fixture trees in the same directory that prove it fires.

| Rule | Meaning |
|---|---|
| `layers` | `entrypoints` → `composition` → (`shell` ∥ `features`) → `core`; `parity-build/` may import `composition` and `core`; no module outside these layers |
| `slice-contracts` | Another slice is reached only through its `contracts.ts`; a slice's `feature.ts` is imported only by `src/composition/registry.ts` |
| `shell-knows-no-slice` | `shell/` imports no slice |
| `pure-model` | A slice's `model/` imports no React, router, query, state or HTTP module, no component and none of its slice's `api/`, `state/`, `hooks/`, `ui/`, `screens/` |
| `ui-without-http` | `core/ui/` and a slice's `ui/` import no `api/` module and no HTTP client |
| `no-raw-http` | `fetch` only in `core/api/` and `core/connection/`; no axios |
| `query-keys-in-keys-modules` | Literal `queryKey` and `mutationKey` arrays only in modules named `keys.ts` |
| `lazy-in-manifests` | React `lazy()` only in a slice's `feature.ts` and in `core/feature/` |
| `no-barrels` | No `index.ts` files and no `export *` |
| `no-cycles` | No static import cycles, type imports included; a dynamic `import()` is not an edge |

## Rules that apply to every file

- At most 200 lines per hand-written source file, CSS included (`scripts/ci/check_repository.py`).
- `@/` is `src/`, in the app, the tests and Vite alike.
- Comments, including doc comments, are in Russian; text shown to users goes through i18n.
