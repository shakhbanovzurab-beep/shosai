# F2 — Frontend foundation: package plan

Prompt: [prompts/F2-frontend-foundation.md](../prompts/F2-frontend-foundation.md). Status: [STATUS.md](../STATUS.md). Decision records: [ADR 0017](../../adr/0017-parity-stand-ins-and-pending-regions.md) (stand-ins and pending regions, CI comparison), [ADR 0018](../../adr/0018-draft-fonts-vendored-in-the-frontend.md) (fonts), [ADR 0019](../../adr/0019-no-session-replay-in-the-cabinet.md) (no session replay), [ADR 0008](../../adr/0008-error-envelope-with-compatible-detail.md) amended (where `request_id` shows), [ADR 0020](../../adr/0020-react-doctor-score-from-the-vendor-service.md) (react-doctor score).

The package builds the `frontend/` project every slice builds its screens into: the Vite and React project, the visual foundation (tokens, Tailwind theme, fonts, icons, themes), the base UI kit, i18n in 16 languages, the data layer with the error envelope and the session, the router with the registration point for slices, the app shell, the analytics bootstrap, and the wiring of the D2 parity harness. It contains no feature screens.

## 1. Facts this plan rests on

### 1.1 Inputs from other packages

| Source | Fact |
|---|---|
| D2, [parity/README.md](../../../parity/README.md), [D2 plan](D2-visual-parity.md) §3.8 | v2 must keep: the SPA under `/app/` with the same paths and query parameters; `wh-auth` (`{state:{csrfToken,user},version:0}`), `wh.theme`, `wh.lang`, `wh.appearance`; fonts at `/fonts/`; texts, roles, `aria-label`s and `data-onboarding` anchors used by states; `prefers-reduced-motion` where the draft honours it; random choices through `Math.random`; `.rise` and `toast-bar` named as in [page-setup.ts](../../../parity/src/determinism/page-setup.ts) or added there. `compare` serves `frontend/dist` and `frontend/dist/fonts` ([parity.config.json](../../../parity/parity.config.json)) and needs only this repository. Replay is strict: a request v2 makes that the draft did not record fails the state; an unexpected `[role=alert]` fails it too |
| D2 baseline | The shell states are `boot.spinner`, `shell.user`, `shell.paid`, `shell.admin`, `shell.desktop-rail`, `shell.mobile-drawer-open`, `shell.connection-lost`, `shell.connection-restored` (plus `shell.support-badge` and `shell.palette.*`, which show S15's badge and S07's palette). Every in-shell screenshot also shows pixels of other slices: the 28 menu entries of 18 draft features, the Leo button (S09), and the page content — `/analytics` (S14) for users, `/download` (S16) for the administrator. Not-found has no baseline: the draft's `*` route leaves the SPA |
| D1, [contracts/README.md](../../../contracts/README.md) | Recorded error bodies are the draft's: `{"detail": "<code or sentence>"}`, `{"detail": {"code": …}}`, `{"error": {...}}`. `web` routes may change together with the v2 frontend. `GET /v1/health` is the connectivity probe. The draft OpenAPI types the shell's endpoints (`UserMeResponse`, `CabinetOut`, `AppBuildOut`, `CostsSummary`, `TokenResponse`, `DetectResponse`) except `/v1/ticker` and `PATCH /v1/me/profile`, which return untyped objects |
| F1, [ADR 0008](../../adr/0008-error-envelope-with-compatible-detail.md) | Errors are `{"error": {code, request_id, params?, fields?}, "detail": …}` with `X-Request-ID` on every response. F2 reads `error.code`, keeps the draft's texts through `errors:<code>` and shows `request_id` for support (§16.2) |
| D4, [FEATURE_MAP.md](../FEATURE_MAP.md) §3.2, §4 | F2 owns the draft's `app/` (router, registry, shell, analytics and i18n bootstrap), `shared/` (api, auth, hooks, i18n, lib, navigation, pwa, query, stores, styles, theme, types, ui, markdown) and `locales/`; F2 hosts `shared/analytics` (catalogue follows S14), `shared/entitlements` (reads S03's contract) and `shared/uploads` (S08's contract); the PWA manifest and icons; draft specs 005, 007, 032, 033, 036, 077, 084. The ticker's backend is S16's |
| CLAUDE.md, [ci.yml](../../../.github/workflows/ci.yml), [check_repository.py](../../../scripts/ci/check_repository.py) | The `frontend` CI job already exists: `npm ci`, `typecheck`, `test`, `build`, `doctor -- --score` = 100, Node from `frontend/.nvmrc`. The 200-line limit covers `.ts`, `.tsx`, `.js`, `.mjs`, `.cjs` and **`.css`** in `frontend/`; a file is exempt under `generated/` or with `@generated` in its first five lines |
| REWRITE_PLAN §2 | Node.js 26.10.0, npm 11 on the host; the harness container runs Node 24.20.0 |

### 1.2 The draft, for lessons

Read in `/root/whisperer/frontend` at the pinned commit `589917e8`. `app/` is 1 900 lines, `shared/` 9 500, plus 3 shared namespaces (`auth`, `common`, `errors`) and one catalogue per feature, each in 16 languages. Stack: React 18.3, react-router-dom 7, TanStack Query 5, zustand 5, i18next 26, Tailwind 4.3.2 without preflight, RetroUI vendored over radix-ui 1.6.2, axios, Vite 6.

| Draft fact | Rule in v2 |
|---|---|
| Features declare routes, menu entries, prefetch, analytics key and shell slots in one `feature.ts` manifest; one registry lists them; the router builder gives every route its own error boundary and `Suspense` | Kept as the registration point (§3.3) |
| The shell imports feature internals: the onboarding store and launcher, the support unread API, the search palette opener, the meetings route helper, the billing cabinet query (`AppShell.tsx:7-17`, `Sidebar.tsx:6-24`, `TopBar.tsx:6-17`) | The shell knows no slice; slices contribute through the manifest and two shell-state contracts (§3.4); the architecture test forbids the import |
| Architecture (15 rules) and i18n checks exist but are not in CI; CI runs Node 20 while the image builds on Node 24 | Both checks are unit tests inside `npm test`; one `.nvmrc` for CI and builds |
| `localeOf` falls back to `zh` (`locales.ts:50`) | Unknown codes fall back to `en` |
| `index.html` repeats the font-role list and the `zh → zh-Hant` map by hand | The pre-paint script is generated from the catalogue, or a test keeps it equal |
| `IconName` is `string`; an unknown name renders nothing | Icon names are a closed union; an unknown name is a type error |
| `Button loading` looks disabled but stays clickable (a known bug kept on purpose); `IconButton` and `Input` keep hover and focus in React state; `Select.tsx` holds a literal NUL byte | `loading` disables the button; hover and focus are CSS; no control characters in sources. The look stays the same |
| Two toast entry points (`toast`, `useToastStore`), two `Section`s, two `CardHeader`s, three toggles | One entry point and one name per thing |
| The ticker ignores `prefers-reduced-motion` (`globals.css:517-540`); the collapsed search tooltip hard-codes ⌘ | Fixed in v2 (owner rule: on-screen defects are fixed, not baselined); the screenshots do not change |
| The route warm-up fetches `/v1/admin/prompts` for every user | A prefetch query carries the route's access rule; no request a screen would not make |
| Yandex Metrika is inline in `index.html` with session replay (webvisor) on; GA4; the edge CSP is report-only with `'unsafe-inline'` | Decision F2-D5; no inline script except the pre-paint one, whose hash F4 can pin |
| 1 603 vendored woff2 slices and 80 generated role stylesheets in `backend/static/webfonts` (59.7 MB), 42 built woff2 in `backend/static/landing/fonts` (1 MB), served at `/fonts/` | Decision F2-D2 |
| `public/onboarding/ru/*.mp3` (3.6 MB), the Excalidraw font plugin, `pwa/sw.js` (push only) | Belong to S01, S06 and S09; not carried by F2 |
| `vite:preloadError` reloads once per 10 s (`main.tsx:17-31`); public entry screens are static, the rest lazy (spec 033) | Kept |

### 1.3 Versions and tool checks (2026-10-02)

Versions from §18.2 are pinned as listed; other packages take the latest stable release on the day a step adds them, then stay pinned in `package-lock.json`.

| Package | Version | Package | Version |
|---|---|---|---|
| react, react-dom | 19.3.0 | vite / @vitejs/plugin-react | 8.3.2 / 6.1.1 |
| react-router | 8.4.0 | typescript | 7.0.2 |
| @tanstack/react-query | 5.104.0 (§18.2; 5.104.1 exists) | vitest / jsdom / @testing-library/react | 5.0.3 / 30.1.1 / 16.3.3 |
| zustand | 5.0.15 | react-doctor | 0.9.14 |
| i18next / react-i18next | 26.4.2 / 17.0.15 | radix-ui / class-variance-authority / clsx / tailwind-merge | 1.6.7 / 0.7.1 / 2.1.1 / 3.7.0 |
| tailwindcss / @tailwindcss/vite | 4.3.3 | openapi-typescript / openapi-fetch | 7.13.0 / 0.17.0 |

Checked in the packages:
- React 19.3.0 exports `ViewTransition`, `Activity` and `useEffectEvent` from the stable build.
- react-router 8.4.0 requires Node ≥ 22.22 and React ≥ 19.2.7.
- react-doctor 0.9.14 brings its own TypeScript (`<6`), oxlint 1.81 and `@sentry/node`; step 1 checks that it runs offline and sends nothing in CI. **Step 1 result:** it does not — the score comes only from the vendor's service, which receives the findings, the repository name and the commit; the supply-chain scan asks Socket.dev about every dependency; telemetry goes to Axiom and Sentry. Decision F2-D7.
- TypeScript 7 is the native compiler. Tools that need the TypeScript JavaScript API are checked against it in step 1 before they are adopted (the architecture test's parser, §3.2). **Step 1 result:** TypeScript 7.0.2 exports only `unstable/*` API entry points, and dependency-cruiser 18.5.0 finds no module in TypeScript sources with it; Vite 8.3.2 exports the oxc parser (`parseSync`, `Visitor`), which reads TSX with UTF-16 offsets and lists static, type-only and dynamic imports.
- Vite 8 bundles with Rolldown; the draft's `manualChunks` does not carry over as is. Step 7 sets chunking from a measurement.

## 2. Decisions

Confirmed by the owner on 2026-10-02 as proposed below; F2-D7 was decided in step 1 against the proposal (the offline gate). Records: F2-D1 and F2-D6 → ADR 0017; F2-D2 → ADR 0018; F2-D3 → ADR 0008 amended; F2-D4 → this plan §3.9 and [FEATURE_MAP.md](../FEATURE_MAP.md) §3.2; F2-D5 → ADR 0019; F2-D7 → ADR 0020.

| ID | Question | Proposal | Trade-off and alternatives |
|---|---|---|---|
| F2-D1 | How is the shell proven before the slices exist, and how does any slice compare before the others? Every in-shell baseline screenshot contains the menu entries of all slices, the Leo button and a slice's page | **Stand-ins and pending regions** (§3.11). A test-only composition in `frontend/parity-build/` adds, for every draft feature no slice has registered yet, its menu entries and routes, and marks its pixels — the page content area, the Leo button — as *pending*. In `compare` the harness masks pending boxes identically in the baseline image and the v2 screenshot. A slice deletes its stand-in when it registers; when the last one is gone the comparison is complete with no masks | Test code of ≈ 200 lines and a harness change of ≈ 100 lines; masks become automatic for pending regions, which narrows D2's rule "every mask has a written reason" to non-pending regions. **Alternative A:** new F2-only states with the slice pixels removed from the DOM in both targets; needs a new baseline upload, and every slice still cannot compare until all others exist. **Alternative B:** prove the shell only after all slices; the prompt's definition of done is not met |
| F2-D2 | Where do the fonts live? Pixel parity needs byte-identical font files | **Vendor the draft's files** that the stylesheets reference (at most 61 MB: ≈ 1 645 woff2 and 80 generated stylesheets; step 2 vendors only the files the stylesheets reference) into `frontend/fonts/`, carry over the role-stylesheet generator, copy them to `dist/fonts/` at build; S17 serves the same directory for the public site | 61 MB of binaries in git history. **Alternative:** `@fontsource/*` packages pinned in the lock file — no binaries in git, but other files and subsets than the draft's, so glyphs may differ by pixels, and Pretendard, D2Coding and Kawkab Mono are not all there. **Alternative:** download at build from the bucket — the build depends on the network and secrets |
| F2-D3 | Where does the user see `request_id`? New UI required by ADR 0008 and §16.2; the draft shows none | In the **error toast** raised by the data layer, as a second muted monospace line «Код запроса: 0199a3c2…» with the full 32-character id; a click copies it. Shown for 5xx and for codes without a translation (the generic message); not for validation, known domain codes or network failures (no response, no id). Two new keys in `errors` in 16 languages, translated by the agent | Draft fixtures carry no id, so parity is unaffected. **Alternative:** on every error toast; noisier for expected errors such as a wrong password |
| F2-D4 | Which draft `shared/` modules does F2 build? D4 placed all of `shared/` with F2 | F2 builds what the shell needs and every module that **two or more slices** import (§3.9 table). A module used by one slice moves into that slice. **Markdown** (react-markdown, Mermaid, MathJax, CodeMirror, lowlight; 2 300 lines; S04, S09, S15) and **uploads** (S07, S08) are built in `core/` by the first slice that needs them, under this plan's rules (spec 032's rules are kept in §3.9) | F2 stays at nine steps and its definition of done needs neither module. **Alternative:** two more F2 steps (markdown, uploads) before any slice can start |
| F2-D5 | Third-party analytics in the cabinet: Yandex Metrika with **session replay** (webvisor records the screen, including meeting text and notes, and sends it to Yandex) and GA4 | Keep the Metrika counter, its goals and the GA4 funnel events as in the draft; **turn webvisor and click maps off** in the SPA; load Metrika from a module instead of an inline snippet | Webvisor is the only part that ships user content to a third party (§14 rule 13, §16.8, nfr-14); the owner loses session recordings of the cabinet. **Alternative:** keep webvisor as in the draft, pending the legal review of §22 |
| F2-D7 | The react-doctor gate: step 1 found that 0.9.14 computes the score only on the vendor's service (decided 2026-10-02, [ADR 0020](../../adr/0020-react-doctor-score-from-the-vendor-service.md)) | **The vendor's score stays the gate** (`--score` prints `100`); the Socket.dev supply-chain scan stays on; telemetry is off through `REACT_DOCTOR_NO_TELEMETRY=1` in the `doctor` script | Every run sends the findings, the repository name and the commit to react.doctor, and the gate needs network. **Alternative:** offline gate with `--no-score --no-supply-chain`, passing on zero findings; nothing leaves the machine, but CLAUDE.md "Checks" changes |
| F2-D6 | Visual comparison in CI | A `parity-compare` job on every push: build the parity composition, run `compare` in the pinned container for the state ids listed in `parity/compare.json` (F2 adds the shell's; each slice adds its own). Reads the baseline with the repository secrets `PARITY_S3_ENDPOINT`, `PARITY_S3_REGION`, `PARITY_S3_BUCKET`, `PARITY_S3_ACCESS_KEY_ID`, `PARITY_S3_SECRET_ACCESS_KEY` — a read-only key limited to `parity-baseline/`, which the owner creates; images cached by manifest hash. **Until the secrets exist, the job reports that it was skipped and passes** (owner, 2026-10-02). Sharded once a run exceeds 10 minutes. The new `route.not-found` baseline (step 8) is uploaded with the credentials D2 used | Until the secrets exist, `compare` is a local check reported by each step |

Design choices made in this plan, accepted by the owner on 2026-10-02:

| ID | Choice | Why |
|---|---|---|
| F2-C1 | Top-level layout mirrors the backend: `entrypoints/`, `composition/`, `shell/`, `features/`, `core/` (the draft's `app/` and `shared/`) | One vocabulary across both projects; `shell/` is a peer of the features, not part of composition, so neither can import the other |
| F2-C2 | Step order differs from the prompt's split: i18n and the data layer come before the shell, the UI kit takes two steps, the parity proof comes with the shell (§4) | The shell renders texts, the session user and four queries; a shell built first could not be compared |
| F2-C3 | `fetch` through openapi-fetch; response types generated by openapi-typescript from the endpoint owner's OpenAPI: the D1 baseline until the owning slice publishes its v2 schema. The first slice with v2 web routes adds the v2 export and moves its modules to it. Untyped draft responses (`/v1/ticker`) get a consumer type next to the call | Contract first (CLAUDE.md); no hand-written copies of server types; axios (13 kB) is not needed for the shell. Upload progress (XHR) is S08's |
| F2-C4 | Server state in TanStack Query, client state in zustand stores in `core/`; query keys only in `keys` modules | §18.2; the draft's rule, now enforced by the architecture test |
| F2-C5 | Data router (`createBrowserRouter`, basename `/app`) with `lazy` routes; a route's loader starts its first query without awaiting it | Chunk and data load in parallel (no waterfall), while navigation still shows the draft's spinner and the screen's own loading state instead of waiting on the old page |
| F2-C6 | No view transitions | The draft has none; an animation users did not have is a visible difference. A slice may propose one to the owner |
| F2-C7 | Not-found keeps the draft's behaviour: a blank screen, then `location.replace` to the public site's `/404/` (`/<lang>/404/` outside ru) with `from`; the page itself is S17's | No visual difference; one not-found page for the site and the cabinet, as the owner decided for the draft |
| F2-C8 | Tailwind without preflight, `dark` variant on `html[data-theme="dark"]`, tokens as CSS custom properties bridged by `@theme inline` | The draft's foundation (spec 077); preflight would change every control's look |
| F2-C9 | The frontend package is `private`, `"license": "UNLICENSED"`, no copy of `LICENSE` | Nothing is published from it; the copy rule applies to packaging metadata |

## 3. Design

### 3.1 Layout

```text
frontend/
  package.json, package-lock.json, .nvmrc (26.10.0), tsconfig*.json, vite.config.ts, vitest.config.ts
  doctor.config.json         react-doctor rules; only design rules may be off, each with a reason (spec 005)
  index.html                 pre-paint script: theme, font role, language (one inline script)
  public/                    favicon, icons, web manifest (root files of the site)
  fonts/                     vendored woff2 and generated roles-<lang>-<role>.css (F2-D2) → dist/fonts
  scripts/                   font stylesheet generator (--check), draft-nav extractor for the parity tests
  README.md                  how a slice registers, its folder template, checks
  src/
    entrypoints/main.tsx     preload-error reload, i18n init, render
    composition/             registry (explicit slice list), router assembly, providers, boot gate
    shell/                   app frame: layout, sidebar, top bar, ticker, connection overlay, not-found, fallbacks
    features/<slice>/        none in F2; public surface: feature.ts (manifest) and contracts.ts
    core/
      feature/               manifest types and pure selectors (nav groups, slots, analytics segments)
      api/                   client, error envelope, generated types, endpoint modules the shell needs
      session/               wh-auth store, refresh, sign-out, forced logout
      query/                 query client and defaults
      i18n/                  locales, detection, catalogue loading, document locale
      theme/                 theme and appearance stores, font catalogue, apply
      styles/                tokens, Tailwind bridge, base, motion, component classes (≤ 200 lines each)
      ui/                    the kit (§3.9)
      hooks/, lib/           shared hooks and pure helpers
      connection/            backend reachability store
      entitlements/          paid state, quota query, premium banner
      shell-state/           contracts the shell and slices share (§3.4)
      analytics/             GA4, Metrika, product analytics SDK
    locales/<lang>/{common,errors}.json
  parity-build/              test-only composition for the harness (§3.11); built to dist-parity/, never deployed
  tests/                     vitest: unit, component, architecture, i18n, fonts
```

### 3.2 Boundaries

An architecture test in `npm test` enforces, with zero allowed violations:

| Rule | Meaning |
|---|---|
| Layers | `entrypoints` → `composition` → (`shell` ∥ `features`) → `core`; `parity-build/` may import `composition` |
| Slices meet through contracts | `features/a` imports `features/b` only through `features/b/contracts.ts`; nothing imports a slice's `feature.ts` except `composition/registry.ts` |
| Shell knows no slice | `shell` imports only `core` |
| Pure model | a slice's `model/` imports no React, router, query or HTTP module |
| UI without HTTP | `core/ui` and a slice's `ui/` import no `api/` module |
| No raw HTTP | `fetch` only in `core/api` (and the connectivity probe); no axios |
| Keys and lazy | query keys only in `keys` modules; `lazy()` only in manifests |
| No barrels, no cycles | no `index.ts` re-export files; no import cycles |

The parser is chosen in step 1: dependency-cruiser if it reads TypeScript 7 sources, otherwise the test reads imports with oxc-parser. Chosen: the oxc parser that Vite exports (`parseSync` from `vite`), no new dependency (§1.3). Slice folder template (README): `feature.ts`, `contracts.ts`, `model/`, `api/`, `state/`, `hooks/`, `ui/` (presentational), `screens/` (route containers), `locales/<namespace>/<lang>.json`.

### 3.3 Registration point

A slice adds one line to `composition/registry.ts` and declares in its manifest:

- `name` and the i18n `namespaces` it owns (each namespace belongs to one slice; `boot` ones load at start);
- `routes`: path, screen (lazy loader that also loads the screen's namespaces), `access` (`public` · `auth` · `user` · `admin`), `outsideShell`, `redirectTo`/`keepSearch`, children, `prefetch` (query + the same access condition), and **layout hints**: `sidebar: "rail"` (document mode), `padding: "none"`, `bottom: "tight"`, `crumbs` (keys of `common`);
- `modalRoutes` (the cabinet over a background page);
- `nav` entries: path, label key, icon, number, group, order, audience, `tag`, optional `badge` hook; the `data-onboarding` anchor is derived from the path (`nav-<path>`), as in the draft;
- `slots`: `root` (above everything), `shell` (inside the signed-in shell), `sidebar-footer`; explicit order, the tour last;
- `analyticsKey` and segments.

Group order, the home route by role, `*`, redirects of composition and the menu numbering check belong to composition. Tests: every route renders inside a boundary and `Suspense`; the menu has no duplicate number, path or anchor.

### 3.4 Shell and its extension points

`shell/` rebuilds `AppShell`, `Sidebar` (full 260 px, rail 66 px, mobile drawer ≤ 860 px, tablet rail 861–1024 px), `TopBar` (ticker, mobile bar with crumbs and profile button), `ConnectionOverlay` and its parts, the full-screen and content spinners, the error fallback, not-found, the theme shortcut Ctrl/Cmd+Shift+L and `--app-content-left`. Draft cross-imports become contracts:

| Draft import | v2 contract |
|---|---|
| `openPalette` (search) | `core/shell-state`: `paletteOpen`; the sidebar button sets it, the search slot reads it |
| onboarding `wantsSidebar`, `phase` | `core/shell-state`: `drawerRequest`; the tour sets it, the shell follows |
| `isMeetingDocPath`, `TIGHT_BOTTOM_ROUTES`, `/calendar` padding, `CRUMBS` | route layout hints (§3.3) |
| support unread queries | `badge` hook on the nav entry |
| `OnboardingLauncher` | `sidebar-footer` slot |
| billing cabinet query (ticker minutes) | `core/entitlements` quota query, shared with S03 by key |

The ticker is the shell's: date, weather, holiday and totals (`/v1/ticker`), minutes left (quota), a tip (`common:ticker.tips`, `Math.random` once per mount), build (`/v1/app/builds`), and for the administrator the rate (`/v1/admin/costs/summary`).

### 3.5 Visual foundation

- **Tokens and Tailwind.** The draft's palette for light and dark, radius scale, `@theme inline` bridge, `@custom-variant dark`, layers imported one by one without preflight, `source()` scan root (spec 077). `globals.css` (947 lines) splits into files of ≤ 200 lines: tokens light, tokens dark, theme bridge, base, typography (`.display`, `.upper`), motion (`.rise`, `.pop`, `.spin`, `.pulse-y`, `.theme-anim`, `toast-bar`, `conn-*`, `.ticker` with `ticker-rtl`), controls (`.btn-press`), RTL (`.rtl-mirror`). Every animation has a reduced-motion rule. RECIPE lessons kept: `text-[Npx]`, logical properties, no bracketed utilities in comments.
- **Fonts (spec 084).** Five roles (`whisperer`, `sans`, `serif`, `native`, `mono`) × 16 languages; the catalogue generates `core/styles/generated/font-roles.css` and `fonts/roles-<hreflang>-<role>.css` (`@generated`); `--check` runs in `npm test`. A test resolves every `url()` to a vendored file. Dev server serves `/fonts/` from `fonts/`; `.woff2` never inlined.
- **Theme.** `wh.theme` = `light` (default) · `dark` · `system` (follows `prefers-color-scheme` live) on `html[data-theme]`; `wh.appearance.font` on `html[data-font]` (default role removes the attribute), adopted from the profile unless edited locally within 5 s; `theme-anim` 400 ms on a switch. The pre-paint script sets theme, font role, `lang` and the role stylesheet before React.
- **Icons.** The draft's 90 inline SVG icons (24 × 24, stroke 1.8, size in em), split into files of ≤ 200 lines; `IconName` a closed union; `MIRRORED_IN_RTL` = chevron, chevronLeft, arrowLeft, send, logout. Logo and sidebar glyphs.

### 3.6 i18n

- 16 locales from one registry (`code`, `hreflang`, endonym, `ogLocale`, `rtl`; `zh` = `zh-Hant`); source `ru`, fallback `en` (never a raw key).
- Detection: `wh.lang` → `navigator.languages` → `GET /v1/i18n/detect` (1.5 s) → `en`; the profile language wins after sign-in; an empty profile takes the local choice by `PATCH /v1/me/profile`. Render waits for the boot namespaces only.
- `html[lang]` and `dir` (`ar` is RTL); a language switch reloads the font role stylesheet.
- Catalogues: F2 carries `common` and `errors` from `src/locales/<lang>/` unchanged (keys stable). `auth` goes to S01, each feature catalogue to its slice under `features/<slice>/locales/<namespace>/<lang>.json`, namespace names as in the draft. Catalogues load with their chunk, one file per language and namespace.
- The i18n test (fail-closed): same keys as `ru` in every language and namespace, no empty values, same `{{placeholders}}`, 2-space JSON with a final newline (specs 007, 036). Dates and numbers through `Intl` with the active locale.

### 3.7 Data layer, errors and session

- **Client.** `fetch` with `credentials: "include"`, base `/v1`; Bearer from the session store; `X-CSRF-Token` from the `meetassist_csrf` cookie (store copy as fallback) on `/auth/` calls; every call takes an `AbortSignal`.
- **Errors.** One `ApiError {status, code, requestId, params, fields}`: `error.code` and `error.request_id` from the v2 envelope (`X-Request-ID` as fallback); for draft-shaped bodies (the harness's fixtures) the code comes from `detail` with the draft's aliases (`Invalid email or password` → `invalid_credentials`, …). Message order as the draft: no response → «Соединение прервано»; `errors:<code>`; 429; 422; 5xx; the caller's fallback. F2-D3 adds the request id line.
- **Session.** Access token in memory only; `wh-auth` persists `{csrfToken, user}` (zustand persist, version 0). Refresh under the Web Lock `wh-auth-refresh`, broadcast on `wh-auth`, one shared refresh per tab, one retry on a CSRF mismatch; a 401 on refresh or a 403 without the cookie ends the session; other failures keep it. A 401 elsewhere refreshes once and retries once. 403 `account_banned` · `account_frozen` · `account_disabled` → error toast, session cleared, `/login`. Sign-out clears the store, the query cache and session-scoped storage.
- **Boot.** `BootGate`: persisted user without a token → full-screen spinner → refresh → routes; then `GET /v1/auth/me` replaces the user without blocking, timezone and appearance follow.
- **Queries.** No retry on 4xx except 408 and 429, one retry otherwise, `staleTime` 30 s, no refetch on focus. A network error starts the `/v1/health` probe (6 s timeout, backoff 1, 2, 4, 8, 15 s); success invalidates all queries and toasts «Соединение восстановлено».

### 3.8 Router

React Router 8 data router under `/app`. Routes outside the shell render with the full-screen spinner, inside it with the content spinner, each in its own boundary and `Suspense`. Access gates: no session → `/login` (replace); `admin` routes → `/analytics` for users; `user` routes → `/dashboard` for the administrator; `/` → home by role. Modal routes render over `backgroundLocation`; the content key ignores cabinet tabs (`contentKey`). Idle warm-up of route chunks one per idle slot, hover and focus preload. `vite:preloadError` reloads at most once per 10 s. Bundle budgets are set from the step 7 measurement and checked by a test on the build manifest (spec 033: entry ≈ 200 kB, no chunk over 500 kB).

### 3.9 UI kit and where the draft's `shared/` goes

Wrappers keep the draft's API and look; the RetroUI primitives stay internal to `core/ui`; refs are props (React 19, no `forwardRef`); variants through explicit maps or cva; no boolean-prop modes where a variant or composition fits.

| Draft module | v2 place | Step |
|---|---|---|
| `lib` (`cn`, format, platform, timezone, money, wav), hooks (media query, latest ref, modal dialog, autosave, debounced value) | `core/lib`, `core/hooks` | 3 |
| Button, IconButton, Spinner, Tag, Kbd, Card, Input, Textarea, Checkbox, Switch, SegmentedToggle, Tabs, PageHeader, EmptyState, settings sections and tokens | `core/ui` | 4 |
| Modal, Popover (+ pointer anchor), ConfirmModal, PromptModal, ContextMenu, HelpTip, Select, Toaster and `toast`, ProviderMark and brand marks, PlatformMark | `core/ui` | 5 |
| api client, session, query, connection, entitlements (paid state, quota, PremiumBanner, PremiumLocked), app version, cabinet paths | `core/*` | 6 |
| feature manifest, lazy screen, analytics | `core/feature`, `core/analytics` | 7, 9 |
| Logo, sidebar glyph, Icon, theme, styles | `core/ui`, `core/theme`, `core/styles` | 2 |
| Markdown, uploads (F2-D4) | `core/`, built by the first slice that needs them | — |
| BarChart → S14; FileGlyph, clipboard → S08; BrandMark → S07; YouTube, service worker → S09; LanguageSwitcher, DesktopDownload, desktop build, Metrika goal helper → S01; retroui calendar → S12 | the slice | — |

Spec 032's rules for whoever builds markdown: no raw HTML (`rehype-raw` never), links `target="_blank" rel="noopener noreferrer nofollow"`, images become links, MathJax SVG through DOMPurify with the SVG profiles, Mermaid with `securityLevel: "strict"`, file previews through DOMPurify.

### 3.10 Analytics

GA4: `page_view` on each navigation, user properties (`auth_state`, plan, locale). Metrika: counter and goals per F2-D5. Product analytics SDK: anonymous id, session, event queue, flush every 5 s, `sendBeacon` on page hide to `POST /v1/analytics/collect`, feature tracking from the manifests' `analyticsKey`; the event catalogue file is carried as generated and owned by S14. Every send fails silently into a counted log, never into the UI.

### 3.11 Parity

- **Stand-ins (F2-D1).** `frontend/parity-build/` reproduces, as data, the 28 menu entries of the draft's 18 manifests (14 user, 14 administrator) for features no slice has registered, with a route per entry whose screen marks the content area (the `main` scroll box) as pending, and a pending box at the Leo button's place (measured on the draft per viewport). Its entry composes the production registry with the stand-ins; `npm run build:parity` builds `dist-parity/` with the production config; `parity.config.json` points `v2` there. Tests: a registered slice has no stand-in; production and stand-in menus together equal `parity-build/draft-nav.json`, extracted once from the draft at the pinned commit.
- **Pending regions.** `data-parity-pending="<slice>"` marks a box of pixels owned by a slice that does not exist yet. In `compare`, after the page settles, the harness takes the visible pending boxes, paints them in the mask colour on a copy of the expected image and masks them in the actual screenshot. A draft widget larger than its box fails the state, so boxes stay honest. `baseline` and `verify` render the draft and never see the attribute.
- **Compare set for F2:** `boot.spinner`, `shell.user`, `shell.paid`, `shell.admin`, `shell.desktop-rail`, `shell.mobile-drawer-open`, `shell.connection-lost`, `shell.connection-restored`, in the cells their baseline has (the full-scope ones: both themes, both viewports, `ru` and `en`). New state `route.not-found`: an unknown deep path; both targets must end on the public site's not-found URL with `from` (a new `expectUrl` field of the state DSL); baseline captured from the draft. `shell.support-badge`, `shell.palette.*` and `route.error-fallback` pass with S15, S07 and S05.
- **CI** per F2-D6: the job checks for the secrets first and passes with a skip notice without them. The harness README gains the stand-in and pending rules.

### 3.12 Performance and security

- Only the active language's catalogues and the boot namespaces load at start; screens, their catalogues and heavy modules load with their route. Static values hoisted; no `useMemo`/`useCallback` without a profile. Polling as the draft (quota 15 s, unread 60 s) pauses in hidden tabs.
- Measured in steps 7 and 8 against the draft's build: entry and route chunk sizes, LCP, CLS and INP of the shell on `vite preview` (targets LCP ≤ 2.5 s, CLS ≤ 0.1, INP ≤ 200 ms), with numbers before and after.
- No token in `localStorage`; no secret in the bundle; one inline script; third-party hosts limited to the analytics of F2-D5; `noindex` on the SPA.

### 3.13 Not in F2

Feature screens, the login and registration screens, the cabinet (S01); markdown and uploads (F2-D4); the service worker and Web Push (S09); NGINX, caching headers, CSP and the image (F4); the public site and its not-found page (S17).

## 4. Steps

Each step is one session, ends with the frontend gates green (typecheck, tests, build, react-doctor 100) and CI green after «Принято».

| Step | Content | Skills | Done when |
|---|---|---|---|
| 1 | **Project skeleton.** `frontend/` with Vite 8, React 19.3, TypeScript 7, the pinned libraries the foundation needs, `.nvmrc` 26.10.0; scripts `dev`, `typecheck`, `test` (single run), `build`, `doctor` (react-doctor 0.9.14 pinned; its telemetry checked); vitest with jsdom; the layout of §3.1; the architecture test (§3.2) with fixture trees proving each rule fires; an entry that renders an empty root; README stub; `.gitignore`; `docs/development.md` "Run the frontend"<br>Done: React 19.3.0, Vite 8.3.2, TypeScript 7.0.2 (`tsc -b` over app, tests and configs), Vitest 5.0.3 with jsdom 30.1.1, react-doctor 0.9.14 — only what the step uses; later steps add their libraries at the §1.3 versions. Architecture test of ten rules on the oxc parser Vite exports, 30 fixture trees, each firing exactly its rule, and a tree of every allowed edge with none; entry test; build target `es2020` as the draft; empty bundle 219.8 kB (68.7 kB gzip). react-doctor scores 100 on the vendor's service, telemetry off (F2-D7, ADR 0020) | the four frontend skills, react-doctor | CI `frontend` job green on the empty project; the architecture test fails on each fixture violation |
| 2 | **Visual foundation.** Tokens, Tailwind bridge, CSS files of §3.5, motion with reduced-motion rules, fonts vendored per F2-D2 with the generator and its `--check`, theme and appearance stores, pre-paint script and its sync test, icons, logo, sidebar glyphs, `public/` root files | the four frontend skills, react-doctor | every font `url()` resolves; tokens defined for both themes; the generator check passes; a render test of every icon |
| 3 | **i18n and core utilities.** Locale registry, detection chain, lazy catalogues, document locale, profile sync hook point, `common` and `errors` in 16 languages, the i18n test; `core/lib` and `core/hooks` of §3.9 | the four frontend skills, react-doctor | the i18n test passes on all 16 languages and fails on a planted missing key and placeholder; detection order covered by tests |
| 4 | **UI kit A: controls and layout** (§3.9 step 4) | the four frontend skills, react-doctor | component tests for roles, labels, keyboard, disabled state and RTL; class strings carried from the draft file by file. The kit's pixels are proven through the shell (step 8) and each slice's compare |
| 5 | **UI kit B: overlays and feedback** (§3.9 step 5); focus trap, Escape and scroll lock as the draft's `tools/perf/a11y.mjs` checks | the four frontend skills, react-doctor | component tests incl. focus return and portals; toast de-duplication, limit 4, durations |
| 6 | **Data layer and session** (§3.7): client, error envelope with draft compatibility, request id line (F2-D3), query client, session store, refresh, forced logout, sign-out, boot gate, connection store and probe, entitlements, app version, ticker and costs queries, generated API types | the four frontend skills, react-doctor | tests: refresh races (two tabs, CSRF mismatch, dead session, network), 401 retry once, envelope and draft bodies, message order, probe backoff; no token persisted |
| 7 | **Router, registration point, parity composition** (§3.3, §3.8, §3.11): manifest types, registry, router builder, gates, redirects, modal routes, boundaries, prefetch and warm-up, layout hints, not-found, nav model; stand-ins, `build:parity`, pending regions and `expectUrl` in the harness; bundle budgets from a measurement | the four frontend skills, react-doctor, Docker ×4 | route tests (access, redirects, modal background, boundaries); stand-in tests; harness unit tests; budgets recorded |
| 8 | **App shell and parity proof** (§3.4): layout, sidebar in three modes, top bar and ticker, connection overlay, theme shortcut; `route.not-found` baselined from the draft; `compare` of the F2 set; the `parity-compare` CI job (F2-D6); shell vitals measured | the four frontend skills, react-doctor, Docker ×4 | **`compare` shows no difference** for the F2 set in both themes and viewports; `route.not-found` passes on both targets; CI green |
| 9 | **Analytics and close** (§3.10): GA4, Metrika per F2-D5, product analytics SDK and feature tracking; frontend README for slices (manifest, namespaces, stand-in removal, compare list); harness README; STATUS `done` | the four frontend skills, react-doctor | the F2 compare set still passes with analytics on (no new request without a recorded or default answer, no error toast); events queued and flushed in tests; the prompt's definition of done holds |

"The four frontend skills": `vercel-react-best-practices`, `vercel-composition-patterns`, `vercel-react-view-transitions`, `web-design-guidelines`. "Docker ×4": the Docker zone skills, for runs of the harness container.

## 5. Risks

| Risk | Mitigation |
|---|---|
| React 19, Tailwind 4.3.3 or Vite 8 render the draft's design a few pixels differently | Found by `compare` in step 8 per state; fixed in CSS, or a per-state tolerance with a written reason; never a global increase |
| react-doctor 0.9.14 flags patterns the draft relied on, or crashes on TypeScript 7 sources | Its own TypeScript is bundled; findings are fixed in code; only design rules may be switched off, each with a reason (spec 005) |
| The pending boxes hide a shell defect under them | Boxes cover only pixels of absent slices; each slice's own compare removes them; the last slice removes the mechanism |
| A stand-in drifts from the draft's menu | `draft-nav.json` test (§3.11) |
| Without the `PARITY_S3_*` secrets CI cannot compare | The job skips and passes (F2-D6); each step reports a local `compare` from the cached baseline meanwhile |
| A slice needs a kit component F2 left out | It adds the component to `core/ui` under this plan's rules in its own step |
| 61 MB of fonts slow `npm ci` caches and clones | Fonts are outside `node_modules`; CI caches only npm; the checkout cost is measured in step 2 |
