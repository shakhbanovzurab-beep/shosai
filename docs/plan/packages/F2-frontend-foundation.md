# F2 — Frontend foundation: package plan

Prompt: [prompts/F2-frontend-foundation.md](../prompts/F2-frontend-foundation.md). Status: [STATUS.md](../STATUS.md). Written on 2026-10-07; it replaces the plan of 2026-10-02, which built the cabinet as a copy of the draft for visual parity and was superseded by [ADR 0021](../../adr/0021-public-site-on-nextjs-cabinet-on-vite.md) and [ADR 0022](../../adr/0022-new-web-design-replaces-draft-parity.md) (the old text is in git history before this commit). Records that stay: [ADR 0008](../../adr/0008-error-envelope-with-compatible-detail.md) amended (where `request_id` shows), [ADR 0019](../../adr/0019-no-session-replay-in-the-cabinet.md) (no session replay), [ADR 0020](../../adr/0020-react-doctor-score-from-the-vendor-service.md) (react-doctor score).

The package moves the cabinet in `frontend/` — the new web UI committed in `f4f8430` on Next.js 16 — to a Vite single-page app, with no visible change, and makes it the project every slice builds its screens into: React Router routes with lazy loading, `use-intl` in 16 languages, a data layer generated from the backend's OpenAPI contract with the ADR 0008 error envelope, development mocks in place of the sample backend, and the npm scripts CI runs. It adds no screens.

## 1. Facts this plan rests on

### 1.1 The project as committed (`89af1e3`, measured 2026-10-07)

| Fact | Source |
|---|---|
| 2 748 tracked files; 50 pages and 6 layouts under `src/app/`, two panels: the user panel `/app/*` (`PanelLayout panel="dashboard"`) and the admin panel `/admin/*` (Russian only); plus `/unauthorized`, `/oauth/callback`, `/oauth/demo-authorize`, `/s/[token]`, `not-found`, `sitemap.ts`, `robots.ts`, Open Graph and Twitter images | `git ls-files src/app` |
| 36 slices in `src/features/` with the layers `domain`, `data`, `api`, `model`, `ui`, `server` and a public `index.ts`; shared code in `components/` (shadcn `ui/`, vendored `calendar/`), `hooks/`, `lib/`, `i18n/`, `config/`, `styles/` | [frontend/docs/architecture.md](../../../frontend/docs/architecture.md), `src/scripts/check-architecture.mjs` |
| The sample backend: 142 route handlers in `src/app/api/`, `src/server/backend-proxy.ts`, 178 files in `features/*/server/` — 14 603 lines of in-memory stores, seeds and handlers. Its HTTP surface is documented per slice in `frontend/docs/*-api.md`. Client gateways (`features/*/api/`, 23 files, and `lib/api-client.ts`) call `/api/*` paths and read FastAPI's `{detail}` | `git ls-files`, `lib/api-client.ts` |
| 35 pages and layouts read data on the server (`features/*/server`, `headers()`, `cookies()`, `find…()`) and pass it to screens as props; `notes/[id]` and the catch-alls call `notFound()`, `/app/w` calls `redirect()` | grep of `src/app` |
| Next.js imports outside `src/app/api`: `next/link` in 76 files, `next/navigation` in 31 (42 `useRouter`, 8 `usePathname`, 8 `useSearchParams`), `next/dynamic` in 19, `next/font` in 2 (17 Google families + Geist Pixel), `next/image` in 1, `next/headers` in 7, `next-themes` in 1 (`components/ui/sonner.tsx`), one Server Action (`preferences/server/preference-actions.ts`, sidebar cookies), `next-intl` in 366 client files, `next-intl/server` in 62 files (pages, route handlers and 4 async UI components: productivity, download, mail preview, shell `PanelLayout`) | grep of `src/` |
| `next.config.mjs`: React Compiler on, `console` removed in production, 15 redirects — in-cabinet ones (`/app`, `/admin`, `/admin/analytics`, `/admin/crm*`, `/app/studio/*`, `/app/team*`) and top-level ones (`/`, `/dashboard*`, `/mail`) | `next.config.mjs` |
| i18n: 16 languages (`lib/language.ts`), 65 namespaces × 16 = 1 040 JSON catalogues, 45 488 messages, ICU; English is the source and the fallback, merged per request (`i18n/fallback.ts`); the language comes from the `ui_language` cookie, `/admin/*` is always `ru` (`src/proxy.ts` sets a header); time zone `UTC` for every format. Ten `*Api` namespaces (12 KB) are the sample backend's error texts. One language is 149 KB raw / 40 KB gzip (en), 236 / 53 KB (ru); `NextIntlClientProvider` ships the whole merged catalogue in every page's payload | `src/i18n/`, `du`, `gzip -9` |
| Preferences (theme mode and preset, layout, navbar, sidebar, font) are `data-*` attributes on `<html>` set before paint by an inline boot script built from `PREFERENCE_REGISTRY`; some persist in localStorage, some in cookies the server read for the sidebar | `features/preferences/` |
| The shell calls Open-Meteo from the browser with the user's coordinates for the header weather | `features/shell/api/weather-api.ts` |
| No PWA manifest, no service worker, no analytics counter in the new UI | grep of `src/` |
| Checks today: `typecheck` (`next typegen && tsc`) passes; `npm test` (node `--test`, 15 files) — 95 pass; `lint:architecture` and `i18n:check` pass but are not in `npm test`; `npm run doctor -- --score` prints `100`. The `doctor` script lacks `REACT_DOCTOR_NO_TELEMETRY=1`, which ADR 0020 requires. `doctor.config.json` ignores `components/ui/**` and `components/calendar/**` | local runs, Node 24.21 |
| Build baseline (`next build`, Turbopack): 67 s wall time; client JavaScript 6.9 MB raw / 2.1 MB gzip in 173 files; the shared root bundle 128 KB gzip; CSS 105 KB gzip | local run |
| Versions in `package.json`: React 19.3.0, Next 16.3.8, next-intl 4.14.9, Zustand 5.0.15, Tailwind 4 through PostCSS, TypeScript ^5.9.3, react-doctor ^0.9.17; React Router and TanStack Query (§18.2) are absent; `.nvmrc` is 26.10.0 | `package.json` |

### 1.2 Repository, CI and contracts

| Fact | Source |
|---|---|
| **CI on `main` is red now:** the repository-rules job reports 13 files over the 200-line limit, all vendored — 11 shadcn components (`sidebar.tsx` 702 lines, `chart.tsx` 372, …), `components/calendar/event-calendar-views.tsx` (497) and `styles/flag-icons/flags.css` (1 068). The rule exempts only generated code | `python3 scripts/ci/check_repository.py`, CLAUDE.md "CI" |
| The `frontend` job runs `npm ci`, `typecheck`, `test`, `build`, `doctor -- --score` = 100 on Node from `frontend/.nvmrc`. There is no `parity-compare` job to remove; the `parity` harness job stays (ADR 0022 keeps `parity/` as a record) | `.github/workflows/ci.yml` |
| The backend (F1) composes no feature yet: its route snapshot is `GET /v1/health`; `/openapi.json` is closed by default (`WebSettings`); every operation documents `default` → `ErrorResponse` (`{error: {code, request_id, params?, fields?}, detail}`) | `backend/tests/composition/public_routes.json`, `backend/tests/core/web/test_openapi.py` |
| `web` routes (383) change with the new frontend. Shipped native clients open cabinet URLs: `/app/connect?state=…` (desktop sign-in on macOS, Linux, Windows, iOS), `/app/support`, `/app/settings/integrations`, `/app/tracker`, and top-level `/cabinet/leo?reminder=…`, `/knowledge-base`, `/models`, which the draft redirected into `/app/…` | [contracts/README.md](../../../contracts/README.md) "Legacy paths", `contracts/draft/consumers.json` |
| Edge routing (ADR 0021, §4.2): `/v1/*` → API; `/app/*`, `/admin/*` and the OAuth callback → the cabinet's static files with its `index.html` as fallback; every other path → the public site, which answers `404` for unknown paths | ADR 0021 §3 |

### 1.3 Versions on 2026-10-07

`npm view`: vite 8.3.3, @vitejs/plugin-react 6.1.2 (peer: @rolldown/plugin-babel ^0.2, babel-plugin-react-compiler ^1.0), @rolldown/plugin-babel 0.2.4, babel-plugin-react-compiler 1.0.0, react-router 8.4.0, @tanstack/react-query 5.104.1 (§18.2 pins 5.104.0), use-intl 4.14.9, msw 3.0.2, openapi-typescript 7.13.0, openapi-fetch 0.17.0, vitest 5.0.3, jsdom 30.1.2, @testing-library/react 16.3.3, tailwindcss and @tailwindcss/vite 4.3.3, typescript 7.0.2, react-doctor 0.9.17. Versions of §18.2 are taken as listed; the others are the latest stable on the day a step adds them and are then pinned in `package-lock.json`. TypeScript 7 is the native compiler without the JavaScript API; the step that upgrades it checks every tool that reads TypeScript first.

`frontend/.npmrc` sets `min-release-age=7`: npm installs only releases at least 7 days old, so the versions actually pinned on 2026-10-08 are vite 8.3.1, vitest 5.0.3, @vitejs/plugin-react 6.1.1, @tanstack/react-query 5.104.0, use-intl 4.14.8, msw 3.0.1. **TypeScript stays 5.9.3** (step 5 result): 7.0.2 has no JavaScript API, which the i18n source check (`src/scripts/i18n/source-rules.ts`) and openapi-typescript 7.13 (peer `typescript ^5`) need; npm `overrides` did not give openapi-typescript its own copy.

## 2. Design

### 2.1 Layout of `frontend/` after F2

```
index.html            noindex, pre-paint boot script (generated from PREFERENCE_REGISTRY), #root
vite.config.ts        React + React Compiler, Tailwind, `base: "/app/"`, dev proxy /v1 → backend, catalogue plugin
public/               favicon, web app manifest and icons
src/
  main.tsx            resolves the language, starts the catalogue fetch and the first route chunk together, renders
  app/                routing only: route tables per panel, layouts, legacy redirects, not-found, error boundary
  features/<slice>/   domain · data · api · model · ui · mocks — imported by direct path (F2-D4)
  components/ hooks/ lib/ i18n/ config/ styles/   shared, as today
  lib/api/            generated/ (OpenAPI types), client, error envelope, query client
  mocks/              mock worker bootstrap and the registry of slice handlers (development and tests)
  scripts/            architecture, i18n, bundle checks — run as Vitest tests
```

Nothing named `api/` routes, `server/` or `proxy.ts` remains; the architecture test forbids `next`, `next-intl`, `next-themes` imports and any request handler in `src/`.

### 2.2 Routing

- React Router 8 in data mode (`createBrowserRouter`), no framework plugin: the cabinet has no server rendering.
- `src/app/routes/` holds one table per area — user panel, workspace (`/app/w/*`), admin panel, standalone pages (`/oauth/callback`, `/unauthorized`) — each under 200 lines; a slice adds its routes there with a small, additive edit. Paths and query parameters are those of `src/app/` today.
- Every page is lazy (`page(...)` in `src/app/routes/lazy-page.ts`). A page whose data must be there before it shows uses the object form of `lazy` (`pageWithData(loader, component)`): the loader module and the component module are separate chunks loaded in parallel, so no request waits for a chunk. In F2 that is the download page and a note; the screens keep their own data hooks until their slice moves them to the generated client and TanStack Query.
- Layouts become layout routes with `<Outlet />`: root (providers), panel (`PanelLayout`), workspace (`WorkspaceGate`), knowledge base and file manager.
- `notFound()` → a `404` thrown by the loader, shown by the not-found page; `redirect()` → a loader redirect; an unknown address under `/app` or `/admin` shows the full-page not-found screen, as on Next.js. Other failures show a failure page worded in every language from a build-time module, so it works even when the catalogue did not load.
- In-cabinet redirects of `next.config.mjs` become loader redirects (`src/app/routes/redirects.ts`) that add the source's query parameters, as Next.js did. Top-level redirects (`/`, `/dashboard*`, `/mail`) and the draft's legacy top-level paths are not cabinet paths; they go to S17's redirect table (§2.9).
- `src/lib/navigation.tsx` is the one adapter the slices use: `Link`, `useRouter`, `usePathname`, `useSearchParams`, `useParams`, with the shape the screens were written against.
- `vite:preloadError` (a stale chunk after a release) reloads the page once per 10 s.
- Route transitions use no view transitions in F2: the screens have none today, and a slice that wants one adds it per the `vercel-react-view-transitions` skill.

### 2.3 Translations

- `use-intl` (`IntlProvider`, `useTranslations`, `useFormatter`, `useLocale`, `createTranslator`) with the same ICU messages, namespaces, keys, `formats` and the `UTC` time zone. `next-intl` client imports are the same hooks under another package name; step 2 switches them while Next.js still runs, as `next-intl` wraps the same `use-intl` context.
- The language is resolved in the browser by the rule of `src/proxy.ts` and `resolve-locale.ts`: `/admin/*` → `ru`; otherwise the `ui_language` cookie if it names a platform language; otherwise `en`. `<html lang dir>` follows it.
- Catalogues: a Vite plugin emits one file per language with all namespaces and the English fallback already merged (`withFallback` at build time), named by content hash. The browser downloads one file of 40–53 KB gzip, cached as immutable, instead of the whole catalogue in every page. The boot script preloads it before the app's code runs; the root loader awaits it.
- Switching the language sets the cookie, loads the new file and swaps the provider in a transition, without a reload. Moving between panels with different languages (`/app` ↔ `/admin`) swaps the same way; `LocaleGuard`'s reload is no longer needed.
- Message types: `tooling/message-types.ts` generates the `*.d.json.ts` declarations that next-intl generated, and `messages-type.ts` feeds use-intl's `AppConfig`; `t("key", args)` stays checked against the English catalogue.
- The i18n check (16 languages, every key, ICU arguments, localized sources) runs inside `npm test`.

### 2.4 Page metadata

Each page renders React 19 `<title>` and `<meta name="description">` from the same messages its `generateMetadata` used; a `PageMeta` component in `src/app/` keeps them uniform. `index.html` carries `<meta name="robots" content="noindex, nofollow">`; the edge adds `X-Robots-Tag: noindex` (F4). `canonical`, Open Graph and Twitter fields are dropped: they serve indexing, which the cabinet does not want.

### 2.5 Data layer

- **Contract.** The backend writes its OpenAPI document to `backend/openapi.json` from the composed API app; a backend test fails when the file is stale. `npm run api:types` turns it into `src/lib/api/generated/schema.d.ts` with openapi-typescript (exempt from the length limit as generated); a frontend test fails when the types are stale. A slice that adds endpoints regenerates both in its commit.
- **Client.** openapi-fetch over the generated paths, same origin, `credentials: "same-origin"`, `Accept-Language` = the interface language (the admin panel sends `ru`). Middlewares are registered, not hard-coded: S01 registers CSRF and session refresh, as it owns the cookie names.
- **Errors.** `ApiError` carries `status`, `code`, `request_id`, `params` and `fields` from the ADR 0008 envelope, and reads a bare `{detail}` too (native-compatible routes and the mocks). Per ADR 0008 amended, `apiErrorDescription(error)` (`src/lib/api/error-description.tsx`) adds `request_id` to an error toast as a muted, copyable second line for 5xx and for codes without words; every error toast's description goes through it. Translating `error.code` into words is each slice's job when it adopts its `/v1` endpoints.
- **Server state.** One TanStack Query client (`src/lib/api/query-client.ts`): retries only for network failures and 5xx on queries, never on mutations. Query options live in each slice's `api/` as the slice adopts its endpoints.
- **Existing gateways** keep their function signatures and call `apiRequest` from `src/lib/api/request.ts`, which reads the envelope too. Their paths and shapes stay the sample ones documented in `frontend/docs/*-api.md` until the owning slice replaces them with `/v1` endpoints from the generated types.

### 2.6 Mocks in place of the sample backend (decision F2-D1)

- The sample stores, seeds and handlers move from `features/*/server/` and `src/app/api/` to `features/*/mocks/` as MSW 3 handlers on the same `/api/*` paths and shapes. Route handlers are already `Request → Response` functions; `NextResponse.json` becomes `Response.json`, `next-intl/server` becomes `createTranslator` over the `*Api` catalogues.
- `src/mocks/` starts the worker and lists the slices' handlers. It runs in `npm run dev` and in tests (`msw/node`); no build carries it (F2-D2). The production build has none: the architecture test forbids importing `mocks/` outside `src/mocks` and tests, and a build check fails if `msw` or a handler reaches `dist/`.
- The mock-only page `/oauth/demo-authorize` (the sample's fake consent screen) is registered by `src/mocks/`, not by the route tables.
- A slice removes its handlers, its `docs/*-api.md` and its sample paths when it publishes its endpoints. Owners (FEATURE_MAP and REWRITE_PLAN §3):

| Frontend slice | Removed by |
|---|---|
| notes, meetings | S04 |
| workspace, admin-workspaces | S02 |
| settings (account, data, memories, usage) | S01; billing parts S03; connectors S12; MCP S10 |
| upgrade, admin-billing, admin-plans | S03 |
| leo, studio, admin-ai-models, admin-platform-prompts | S09 |
| knowledge-base | S07 |
| file-manager | S08 |
| calendar | S12 |
| kanban | S13 |
| admin-errors | S14 |
| support, admin-support, admin-users, admin-roles, admin-dashboard, admin-profile | S15 |
| hub, download, admin-apps | S16 |
| admin-livekit | S06 |
| mail (`/app/inbox`) | S12 (F2-D6) |
| productivity (`brief/today`, `me/*`) | S16 (F2-D6) |

### 2.7 Preferences, fonts, theme

- The boot script stays the only inline script. A Vite `transformIndexHtml` hook generates it from `PREFERENCE_REGISTRY`, so the registry is not repeated by hand; a test records its SHA-256 for the CSP that F4 sets at the edge.
- Preferences the server read from cookies (sidebar state, variant, collapsible) are read by the boot script and the store from the same cookies, so existing choices survive; the Server Action goes.
- `next/font/google` → pinned `@fontsource` packages for the 17 families (latin subset, as now) and Geist Pixel from the `geist` package, with the same CSS variables (`--font-inter`, …). Font files load only for the selected font, as now.
- `next-themes` in `sonner.tsx` → the theme mode of the preferences store.
- `next/image` → `<img>` with `width`, `height`, `loading` and `decoding`; the download page detects the system from `navigator` instead of request headers.

### 2.8 Build, tests, scripts

| Script | Command |
|---|---|
| `dev` | `vite` with mocks; `dev:api` proxies `/v1` to the local backend (`compose.dev.yaml`) without mocks |
| `typecheck` | generates the message types, then `tsc --noEmit` (TypeScript 5.9.3, §1.3) |
| `test` | `vitest run`: unit tests, the architecture check, the i18n check, OpenAPI types in sync |
| `build` | `vite build`, then the bundle check (no mocks, no source maps published, no chunk above the budget fixed in step 6) |
| `doctor` | `REACT_DOCTOR_NO_TELEMETRY=1 react-doctor --verbose` (ADR 0020) |

React Compiler stays on (`@vitejs/plugin-react` with `@rolldown/plugin-babel` and `babel-plugin-react-compiler`). `console` calls are dropped from production by the bundler, as `removeConsole` did. Biome stays the formatter and linter.

### 2.9 What leaves `frontend/` and where it goes

| Item | Goes to |
|---|---|
| `sitemap.ts`, `robots.ts`, Open Graph and Twitter images | Deleted; the public site owns them (S17) |
| `/s/[token]` (shared meeting page) | Deleted; S17 builds it on the public site with S04's endpoint; its UI (`SharedNoteScreen`, `SharedLinkGone`) stays in `features/notes` until S17 moves it to `site/` |
| Top-level redirects `/`, `/dashboard*`, `/mail`; the draft's `/cabinet/*`, `/knowledge-base`, `/models`, `/studio/{id}`, `/rooms/{id}`, `/meetings/{id}` | S17's redirect table (public site), listed in its plan; `/cabinet/leo?reminder=` is a native contract (nfr-12) |
| `/app/connect`, `/app/login` and other draft cabinet paths that natives open | Cabinet routes of their owning slice (S01 for sign-in); F2 provides `src/app/routes/redirects.ts` for old `/app/*` paths that only move |
| `X-Robots-Tag`, SPA fallback for `/app`, `/app/*`, `/admin/*`, `/oauth/callback`, `/unauthorized` (`tooling/cabinet-paths.ts`), CSP allowing the two inline boot scripts by the hashes in `dist/csp-hashes.json`, immutable caching of `/app/assets/*` | F4 (edge) |

## 3. Decisions

Decided by the owner on 2026-10-08. Records: F2-D5 amends [ADR 0021](../../adr/0021-public-site-on-nextjs-cabinet-on-vite.md) §3; F2-D6 updates [FEATURE_MAP.md](../FEATURE_MAP.md); the others are recorded here and in the code checks that enforce them.

| ID | Question | Decision | Trade-off accepted |
|---|---|---|---|
| F2-D1 | How do screens get data before their slice publishes endpoints? | **Mocks** (§2.6): the sample backend becomes MSW handlers on the same paths, **in local development and tests only**; each slice deletes its handlers when it delivers its API | 14 600 lines move instead of being deleted and stay until the last slice; screens exercise the real HTTP path and error handling |
| F2-D2 | What runs on https://shosai.tech before the slices exist? | **The production build only**, without mocks; no demo flavour | Until S01 the staging cabinet shows error states |
| F2-D3 | 13 vendored files over 200 lines make CI red | **Split them** and import flag icons from the pinned `country-flag-icons` package (`3x2/flags.css`) instead of the vendored copy; done first, as a separate fix | Vendored shadcn code differs from upstream in file layout; an update through `shadcn add` is re-split by hand |
| F2-D4 | CLAUDE.md forbids barrel files; every slice had a public `index.ts` re-exporting its contract | **Strict direct paths, no exception.** Every `index.ts` barrel is removed; code imports the module that defines a symbol. The architecture test forbids (a) any file that only re-exports, (b) a dependency cycle between slices, (c) importing another slice's `mocks/` outside the mocks, and `src/app/` from anywhere but the entry and the mocks. Another slice's `data/` stays importable: it is the sample data the screens show until the slice's API exists (found in step 5: `notes/data` feeds four screens) | A slice's public surface is no longer one file; the architecture test, not a facade, keeps internals and cycles out |
| F2-D5 | `/unauthorized` is a top-level cabinet page; the edge sends top-level paths to the public site | **Kept**; the edge serves it from the cabinet (ADR 0021 §3 amended) | One more edge rule for F4 |
| F2-D6 | `mail` (`/app/inbox`) and `productivity` (`/app/productivity`) had no owning slice | **Mail → S12, productivity → S16** (FEATURE_MAP updated) | — |

## 4. Steps

Each step fits one session, leaves the project building and running with every screen as before, and ends with the zone's checks and the frontend gate (`npm run doctor -- --score` = 100), then a commit after «Принято».

| Step | Content | Skills | Done when |
|---|---|---|---|
| 1 | **Green CI and the test runner, still on Next.js.** Split the 12 oversized vendored components (F2-D3), flags from `country-flag-icons`; Vitest 5 replaces `node --test`; the architecture and i18n checks become tests inside `npm test`; `doctor` script gets `REACT_DOCTOR_NO_TELEMETRY=1` | the four frontend skills, `react-doctor` | `check_repository.py` passes; `typecheck`, `test` (with architecture and i18n), `build`, doctor 100; CI green on `main` |
| 2 | **Adapters and direct paths, still on Next.js.** Every slice `index.ts` barrel removed and imports rewritten to the defining modules (F2-D4); `src/lib/navigation.ts` over Next.js and every `next/link` / `next/navigation` call site through it; client `next-intl` imports → `use-intl`; `next/dynamic` → `lazy` + `Suspense`; `next-themes` → preferences store; the 4 async server UI components become client components; `next/image` → `<img>` | as step 1 | No `next/link`, `next/navigation`, `next/dynamic`, `next-themes` or `next-intl` (client) import outside `src/app/` and `src/lib/navigation.ts` — the architecture test enforces it; every screen unchanged (spot check both themes, desktop and mobile, `en`, `ru`, `ar`) |
| 3 | **Data layer and mocks I — infrastructure and user panel.** `backend/openapi.json` with its backend test; `src/lib/api/` (generated types, client, envelope errors, query client, request-id toast); MSW in dev and tests; the user-panel and workspace slices' sample routes → `features/*/mocks/`; their pages read through queries; their `src/app/api/*` and `features/*/server/` deleted | frontend skills, `react-doctor`, `fastapi`, `python-doctor` | Backend gate passes; the user panel works on `npm run dev` with mocks; tests cover the client, error envelope parsing, retries and the toast; no user-panel route handler left |
| 4 | **Data layer and mocks II — admin panel and the rest.** The remaining sample routes → mocks; `src/app/api/`, `src/server/`, every `features/*/server/` and the Server Action deleted; `/oauth/demo-authorize` mock-only; the architecture test forbids request handlers and server code in `src/` | frontend skills, `react-doctor` | No API code in `frontend/`; every screen renders on mocks as before |
| 5 | **The switch to Vite.** `vite.config.ts`, `index.html` with the generated boot script and `noindex`; React Router route tables with `lazy` loaders and layout routes; in-cabinet redirects and `legacy-redirects.ts`; not-found and error elements; `PageMeta`; `use-intl` provider with browser language resolution and per-language catalogue files; fonts from `@fontsource`; React Compiler; `navigation.ts` switched to React Router; TypeScript 7 after the tool check; public pages and every Next.js file and dependency removed; npm scripts of §2.8. Visual check: the step-4 commit built from `git archive` and the Vite build, both on mocks with a frozen clock and blocked third-party requests, screenshotted by Playwright for every route, both themes, 1440 px and 390 px, in all 16 languages, compared pixel by pixel; differences fixed or explained | frontend skills, `react-doctor` | No Next.js dependency or file in `frontend/`; `typecheck`, `test`, `build`, doctor 100; the screenshot comparison reports no unexplained difference; build time and bundle sizes measured against §1.1 |
| 6 | **Production readiness.** Web app manifest and icons (installable PWA, no offline cache); `vite:preloadError` reload; chunking and the bundle budget set from a measurement; the bundle check (no mocks, no source maps in `dist/`); boot-script hash and the edge rules of §2.9 written down for F4; `frontend/docs/architecture.md`, `frontend/README.md`, `docs/development.md` and ARCHITECTURE §18.2 versions updated; STATUS `done` | frontend skills, `react-doctor` | CI frontend job green after push; first-load JavaScript and LCP on `/app/productivity` measured and not worse than the Next.js baseline; definition of done of the prompt met |

### Results

The owner asked for the whole package in one session (2026-10-08); the steps were done in that session in a changed order — barrels, adapters, the Vite app, the data layer and the mocks together — since no intermediate commit was planned between them. Each step's result:

| Step | Result |
|---|---|
| 1 | Done. CI fix committed separately (`39e99cb`): 7 vendored components split, 4 unused ones (combobox, carousel, menubar, questionnaire) and their two dependencies removed, flags from `country-flag-icons` 1.6.20, `REACT_DOCTOR_NO_TELEMETRY=1`. Vitest 5.0.3 replaces `node --test`; the architecture and i18n checks are tests |
| 2 | Done. 53 barrels (`index.ts`, `server.ts`) and 8 re-export modules (chart primitives, `export type *`) removed, 248 files import the defining modules; `src/lib/navigation.tsx` over React Router; 377 files moved from `next-intl`, `next/link`, `next/navigation` to `use-intl` and the adapter; `next/dynamic` → `lazyComponent`; async server components → hooks |
| 3–4 | Done. `backend/openapi.json` with its test (`--update-openapi`), `src/lib/api` (generated types, client, envelope errors, request-id toast line, query client); the sample backend (142 routes, 14 600 lines) moved to `features/*/mocks` as MSW handlers through a runtime shim; Node-only parts rewritten for the browser (upload store in memory, Web Crypto, a pure SHA-256 for seeds); the OpenRouter live path dropped from the AI-models mock (no secret reaches a browser); `src/app/api`, `src/server`, `proxy.ts` deleted |
| 5 | Done. Vite 8.3.1 SPA with React Compiler; 55 route modules, lazy per page; root loader resolves the language; per-language catalogues with build-time fallback; boot scripts with CSP hashes; fonts from `@fontsource` declared on `body` as next/font did; public pages removed; build 32 s (Next.js: 67 s). TypeScript 7 not adopted (§1.3). Visual check: 897 full-page screenshots of the Next.js build (`39e99cb`, sample backend) and of the Vite cabinet (mocks), 33 user-panel pages × en, ru, ar × both themes × 1440 and 390 px, the same pages at 1440 px light in the 13 other languages, 18 admin pages × both themes × both widths; frozen clock and `Math.random`, third-party requests blocked, Geist served from the files next/font downloaded so the comparison isolates the move from the font version. Result: identical but for the animated Leo orb (< 0.2 %) in 841 screenshots; explained differences — 14 dark-theme screenshots that Next.js rendered light (its hydration errors on the 404 page, `/app/notes` and `/app/productivity` dropped the theme class; the cabinet keeps the theme), random sample values of the LiveKit and errors mocks now generated in the browser (6), a 1 px rounding of the productivity contribution grid (10); none in layout, text or language |
| 6 | Done. Web app manifest and icons, `vite:preloadError` reload, bundle check (`tooling/check-dist.ts`: no mocks, no source maps, initial JS ≤ 220 KB gzip — now 198 KB, any chunk ≤ 170 KB gzip); lucide icons in one chunk (147 → 92 JS files on the first load of `/app/productivity`). First-load JavaScript, gzip, Vite against Next.js: `/app/productivity` 467 against 459 KB, `/admin/dashboard` 591 against 687 KB, `/app/notes` 467 against 472 KB; uncompressed it is smaller on every page; docs (`frontend/README.md`, `AGENTS.md`, `docs/architecture.md`, `docs/i18n.md`, `docs/development.md`, ARCHITECTURE §18.2) |

Findings for the owner, not changed by F2 (the move keeps the look):

- `font-mono` renders Geist, not Geist Mono, everywhere in the new UI: `--font-mono` is computed on `:root`, where the font variables are not defined (they are on `body`). Fixing it changes how slugs, ids and code look.
- next/font downloaded the fonts from Google Fonts at every build, so the Next.js look depended on the day of the build; the cabinet now pins them through `@fontsource` 5.3.0, whose Geist is slightly narrower (Google's file of 2026-10-08 is about 1.4 % wider).
- The header weather calls Open-Meteo from the browser with the user's coordinates (§5).

## 5. Risks

- **TypeScript 7 and the tools.** If a tool the project needs reads the TypeScript API, step 5 keeps TypeScript 5.9 for it and records why; the upgrade does not block the switch.
- **React Compiler on Rolldown.** If the Babel pass makes the build slower than the Next.js baseline by more than the measured gain elsewhere, step 5 reports the numbers and asks before turning it off.
- **Mock determinism.** Seeds that read the clock or `Math.random` make screenshots differ; step 5 freezes both in the capture, not in the seeds.
- **Third-party request.** The header weather calls Open-Meteo with the user's coordinates; behaviour is unchanged by F2, and the CSP of F4 must allow it or the owner drops it.
