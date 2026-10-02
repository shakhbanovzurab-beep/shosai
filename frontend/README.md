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
| `npm run build` | Production bundle in `dist/` (base `/app/`), plus `public/` copied to `dist/` and the fonts to `dist/fonts/`; the parity harness serves it |
| `npm run fonts` | Rewrites the font stylesheets from the font catalogue; `-- --check` only compares (`npm test` runs the same comparison) |
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
| `public/` | Root files of the site, served at `/` with the draft's URLs: favicons, app icons, the install manifest shared with the landing |
| `fonts/` | The draft's woff2 files, byte-identical ([ADR 0018](../docs/adr/0018-draft-fonts-vendored-in-the-frontend.md)), their manifest `faces.json` and the generated `roles-<lang>-<role>.css`; served at `/fonts/` |
| `scripts/` | Node tools run by npm scripts and Vite: the font stylesheet generator, the plugin that serves and copies `public/` and `fonts/` |
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

## Styles, theme and fonts

- `src/core/styles/main.css` is the only stylesheet entry. Tailwind v4 is configured there, its layers imported one by one **without preflight**; our rules live in `@layer components`, so a utility of the same property wins over them. Palette tokens and font rules are unlayered.
- Colours come from the tokens in `tokens-light.css` and `tokens-dark.css` (the same names in both, checked by a test) through the Tailwind bridge in `theme-bridge.css`: `bg-primary`, `text-muted-foreground`, `border-hairline` and the like. The `dark:` variant follows `html[data-theme="dark"]`.
- Every animation stops under `prefers-reduced-motion` unless it carries state (`.spin`, the toast countdown); a test checks it. The parity harness names `.rise` and `toast-bar`; keep those names.
- Font sizes are in `rem`, never `text-[Npx]` or `font-size: Npx` (a test checks it), so the browser's text zoom works everywhere.
- The theme and the font role are applied before the first paint by the one inline script in `index.html`; `startTheme()` in the entry repeats it and keeps `useThemeStore` in sync. The font catalogue (`src/core/theme/fontCatalogue.ts`) is the single source of the role mapping; `npm run fonts` regenerates the stylesheets from it.
- Icons: `<Icon name="…" />` with a closed `IconName` union; glyphs that point along the reading direction mirror themselves in RTL.
- The CSS build target is Tailwind v4's browser baseline (Safari 16.4, Chrome 111, Firefox 128): lowering CSS further broke keyframes with logical properties. The JavaScript target stays ES2020.

## Rules that apply to every file

- At most 200 lines per hand-written source file, CSS included (`scripts/ci/check_repository.py`).
- `@/` is `src/`, in the app, the tests and Vite alike.
- Comments, including doc comments, are in Russian; text shown to users goes through i18n.
