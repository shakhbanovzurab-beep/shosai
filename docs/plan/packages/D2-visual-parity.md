# D2 — Visual baseline and parity harness: package plan

Prompt: [prompts/D2-visual-parity.md](../prompts/D2-visual-parity.md). Status: [STATUS.md](../STATUS.md). Decision record: [ADR 0003](../../adr/0003-playwright-visual-parity-harness.md).

The harness proves that a v2 screen looks like the draft screen. It renders the draft and v2 from identical recorded API data, in a pinned browser, and compares the screenshots per route and state.

## 1. Facts this plan rests on

**Draft pinned at** `589917e847f7d7213b3af5a3959bcc88c7500fe7`. The baseline, the fixtures and the inventory refer to this commit. Moving the pin means re-recording and re-capturing.

**Inventory** ([parity/inventory/](../../../parity/inventory/README.md)): 55 route paths plus the cabinet modal route; about 850 states in 5 group documents. Every declared path is covered.

**Pilot** (2026-10-01, scratch, not committed). Setup:
- the draft built at the pinned commit and served through Playwright request interception;
- 10 screens on desktop and mobile, light and dark, `ru` = 40 screenshots;
- Playwright 1.63.0 in the image `mcr.microsoft.com/playwright:v1.63.0-noble@sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27` (Chromium build 1243).

| Measured | Result |
|---|---|
| Size | 57 KB per PNG on average, at device scale factor 1 (25–108 KB) |
| Page height | Equals the viewport. The app scrolls inner containers, not the page, so a full-page screenshot captures only the viewport. Content below the fold needs its own scrolled state. |
| Speed | About 1 screenshot per second with 4 workers on this host (4 CPU, 7 GB) |
| Wrong screens | 8 of 40 failed the marker check. The draft's own hand-written fixtures did not render the intended screen on mobile and analytics. Markers are mandatory. |
| Determinism, first attempt | Every screen differed between two runs by about 4 300 px. Cause: the ticker's tip of the day is chosen by `Math.random()` (`app/shell/TopBar.tsx:118`). |
| Determinism, second attempt | Two mobile screens alternated between two renderings (23 px and about 4 000 px). Cause: entrance animations (`.rise`) left text rasterized at a fractional offset; whether it was repainted before the shot varied. Raster flags (`--disable-lcd-text`, `--disable-partial-raster`) did not help. |
| Determinism, final | Seeded `Math.random`, animations and transitions set to zero from document start, then wait for marker, fonts loaded, 500 ms without requests and 500 ms without DOM mutations. **4 repeats × 32 screenshots: 0 px difference.** |

## 2. Matrix and volume

| Axis | Values |
|---|---|
| Viewport | desktop 1440 × 900; mobile 390 × 844 with touch (mobile layout is ≤ 860 px). Device scale factor 1. |
| Theme | light, dark (`wh.theme`) |
| Locale | `ru` and `en` |
| Scope | **full**: all 8 cells (viewport × theme × locale) for the main states of a screen; **single**: one cell — `ru`, desktop, light — for small variants (decision 2, §5) |
| Locale sweep | the 14 other locales (`ar de es fr hi id it ja ko pt th tr vi zh`) on one text-dense signed-in screen — `meetings.library.populated` — desktop and mobile, light |
| Fixed | clock `2026-07-17T12:00:00Z` (a Friday, 15:00 in Moscow), timezone `Europe/Moscow`, `Math.random` seed, pointer parked at (0, 0) |

Tablet (861–1024 px, rail sidebar) is not in the prompt's matrix and is not covered.

| Volume | Estimate |
|---|---|
| States × cells | between ≈ 3 800 (if half of the states are variants) and 6 800 (if none are) + 28 in the locale sweep; counted exactly as the state definitions are written in steps 3–7 |
| One full baseline | ≈ 220–390 MB |
| One full run | ≈ 1–2 hours on this host; shards across runners |
| One slice | tens to a few hundred screenshots; minutes |

## 3. Design

### 3.1 Layout

```text
parity/
  README.md                  how a slice runs the comparison and adds its states
  package.json, package-lock.json, tsconfig.json, .nvmrc
  compose.yaml               harness container (pinned image); draft recording stack
  playwright.config.ts       one project per matrix cell
  parity.config.json         pinned draft commit, v2 build paths, clock, time zone
  scripts/parity.sh          baseline / verify / compare
  src/
    targets/                 draft and v2: which files to serve
    serve/                   static files, SPA fallback, fonts; third-party stubs; everything else blocked
    replay/                  strict fixture router and the closed list of background requests
    determinism/             init script and the settle step
    states/<feature>.ts      typed state definitions; registry.ts lists them
    i18n/texts.json          translation texts used by markers, generated from the draft
    baseline/                manifest and S3 store
    contracts/               validation of synthetic responses against the draft OpenAPI (D1)
    recording/               recorder, visits, normalizer
    parity.spec.ts           one test per state, tagged with its cells
  fixtures/<visit>.<lang>.json
  recording/                 draft API image, seeds, record.sh
  inventory/                 route and state inventory
  baseline/manifest.json     state, cell, SHA-256 and size of each image; the PNGs live in S3
```

The harness is its own npm project. It runs inside the pinned Playwright container, so the browser, its fonts and Node are the same on every machine and in CI.

### 3.2 Targets

A target is a built frontend plus the static files it needs, served at the origin `http://parity.localhost` by request interception. No server process is involved. A `.localhost` origin is a secure context, as HTTPS is in production, so the browser exposes the APIs that only secure contexts get: the microphone, AudioWorklet and push.

- **draft**: `git archive` of the pinned commit (the draft tree is never touched), `npm ci`, `vite build` into the harness cache. Fonts come from the draft's `backend/static/landing/fonts` and `backend/static/webfonts`, served at `/fonts/` as the draft backend serves them.
- **v2**: `frontend/dist` of this repository and v2's own font directory, set in `parity.config.json`; F2 adjusts the paths when the frontend exists.

Requests to any other host are aborted: analytics, the CloudPayments widget and the rest. The Yandex, VK and Google sign-in SDKs and the Turnstile captcha get stubs. Blocked, they make the draft show an error toast that users never see.

### 3.3 Fixtures and replay

- A fixture is the recording of one visit in one language: the persona's storage and every `/v1` exchange (method, path, query, status, body, `origin`). Visits are recorded in `ru` and `en`, because some requests carry the language.
- Streams and sockets belong to the state, not to the fixture: their content comes from a model, a voice provider or a scheduler that the recording stack does not have.
  - A finished server-sent event stream is an ordinary reply with the whole body.
  - A stream still being written is an open stream. A shim over `fetch` in the page sends its events and never ends it.
  - WebSocket frames for `/v1/ws/...` are a script on the state: frames on connect and frames after the page's first message (step 5).
  - A socket to another host, the LiveKit media server, is closed; a script for it with no frames keeps the room connecting (step 6).
  - The conversation of Leo lives in the browser, so the state seeds it into localStorage.
- A state is a **fixture** + **overrides**: an error status, an empty list, a held request for the loading state, a network failure. Each override is synthetic and needs a reason.
- File previews read content the recording stack cannot serve without S3. A state answers `content` with text or bytes (sample DOCX and XLSX built in memory), and points a synthetic `download-url` at a stand-in object store that serves a sample image and PDF (step 6).
- A short, closed list of background requests is answered by default when a fixture lacks them, because they fire later than a recording ends: analytics flushes, the satisfaction prompt after 25 s, the connection probe.
- Replay is strict. A request with no matching response fails the test and is reported by name. The draft's tool answered unknown paths with `[]`, which made broken screens look clean.
- Recorded fixtures have the draft's real shapes by construction. Synthetic fixtures are validated in CI against the draft's OpenAPI from D1 (`contracts/draft/`), so an invented or renamed field fails before any screenshot is taken.

### 3.4 State definitions

A typed record per state:
- id;
- persona;
- URL;
- scenario and overrides;
- interactions;
- marker;
- matrix scope: `full` or `single`;
- optional per-state tolerance with a reason.

Scope rule:
- **`full`** covers the main states of a screen: populated, empty, loading, page-level error, every dialog, drawer, menu and tab, the paywall, and the first step of a sequence.
- **`single`** covers variants that differ from a `full` state of the same screen only by a message or a step:
  - one toast per error code;
  - inline validation hints;
  - password-strength levels;
  - tour steps after the first, and audio stops;
  - sibling states written as `a` / `b` / `c` in the inventory.
- A state whose layout changes is `full`, for example when a banner pushes content down or a panel opens.

Selectors use roles, `aria-label`, visible text and `data-onboarding` anchors, so the same definition drives the draft and v2. Visible texts come from the draft's translation catalogs by key (`t("auth:titleLogin")`, generated into `src/i18n/texts.json`), so one definition works in all 16 languages. Draft class names are used only where nothing else exists (`.onb-card`), so F2 can keep them or replace the selector.

A state can also restrict its viewports (the mobile drawer exists only on a phone), mask a region that follows real time (a "resend in 60 s" countdown) or a live device (the fake camera's picture), and raise its tolerance. A mask and a tolerance each need a written reason. It can set the browser's answer to the camera request (denied, or never answered) and sessionStorage keys (step 6).

### 3.5 Determinism

The pilot recipe, applied to every state:
- frozen clock and time zone;
- seeded `Math.random`;
- "reduce motion" emulated: the draft then stops the sign-in poster and Leo's gaze, which otherwise change every frame;
- animations and transitions zeroed from document start, except animations whose end changes the screen: the draft's toast closes when its `toast-bar` animation ends, so that animation stops on its first frame;
- entry animations whose last frame is the element's own style (the draft's `.rise`) removed: a filled zero-length animation of opacity and offset sometimes put the element on a composited layer, and its anti-aliasing moved by one colour level (step 7);
- pointer parked;
- captcha and sign-in SDK stubs;
- service workers blocked;
- a secure-context origin (`http://parity.localhost`) and a fake microphone and camera, so voice, recording, push and the room preview render as in production (step 5, camera in step 6);
- a silent Web Speech recogniser: the meeting assistant listens and hears nothing, and no audio leaves the browser (step 6);
- an interaction starts only once the page has settled (fonts loaded, 500 ms without API requests and DOM changes) (step 5);
- Chromium partial raster off: an interaction on a drawn page otherwise redraws only the changed rectangles inside existing tiles, and anti-aliasing at their edges varied from run to run (step 5);
- greyscale text anti-aliasing (`--disable-lcd-text`): Chromium draws subpixel text only outside composited layers, and blocks with an entry animation entered and left a layer depending on timing, so the same text came out coloured or grey (step 5);
- then marker, fonts, 500 ms without API requests and 500 ms without DOM changes before `toHaveScreenshot`;
- a state scrolled to content below the fold scrolls only after that wait, always to the same position (the marker centred in its scroll area), and waits again (step 5). Scrolling earlier, or only "if not visible", left a position that depended on when the blocks above finished loading.

Measured in step 3: the 237 screenshots of steps 2–3, captured from scratch and restored from S3, matched with zero tolerance in every run.

Measured in step 3b: 145 states, 430 screenshots, 31.7 MB in the bucket; `baseline` and two `verify` runs matched with zero tolerance. Masks cover two regions driven by real timers: the resend countdown on the code screen and the `mm:ss` stamps of the connection log.

Measured in step 4: 315 states, 775 screenshots, 59.2 MB in the bucket; `baseline` and two `verify` runs matched with zero tolerance. The seed now holds meetings, so the ticker's meeting count changed on every signed-in screen: all visits were recorded again (twice, byte-identical) and every screenshot was re-captured.

Measured in step 5: 495 states, 1063 screenshots, 86.3 MB in the bucket; `baseline` and two `verify` runs matched with zero tolerance, the first restoring every image from S3. All 70 visits were recorded twice, byte-identical.
- **What made it repeatable.** Four harness rules above came from failing `verify` runs: an interaction waits for a settled page, a scrolled state centres its marker after that wait, partial raster is off, and text is greyscale. The last one re-rendered every screenshot.
- **Data changes on earlier screens.** The new seed shows only where its data appears:
  - the ticker's AI answer and token totals, from the seeded AI spend;
  - the Acme hub on meeting chips and library cards;
  - the origin `parity.localhost` in share, referral and iCal links.
- **Masks.** One mask was added: the waveform and timer of the Leo voice recorder.

Measured in step 6: 663 states, 1346 screenshots, 100.2 MB in the bucket; `baseline` and two `verify` runs matched with zero tolerance, the first restoring every image from S3. All 100 visits were recorded twice, byte-identical.
- **Data changes on earlier screens.** One earlier screenshot changed: `shell.palette.results`, because the palette search now also finds a seeded tracker task. The new personas raise the user count in the admin data, which no earlier screen shows.
- **Masks.** One mask was added: the fake camera's moving picture in the room preview.
- **Harness browser limits.** Chromium headless shell has no PDF viewer and formats native date fields by its build, not by the page locale; both targets are drawn in the same browser, so the comparison is unaffected (inventory, «Coverage in the screenshot matrix», step 6).

Measured in step 7: 833 states, 1573 screenshots, 121.9 MB in the bucket; `baseline` and two `verify` runs matched with zero tolerance, the first restoring every image from S3. All 115 visits (215 fixtures) were recorded twice, byte-identical.
- **What made it repeatable.**
  - The recording API's wall clock stands still, so window starts such as "the last 30 days" no longer drift between runs.
  - The normalizer sorts groups the draft returns in database order (`UNORDERED_GROUPS`: dashboard breakdowns, onboarding steps and actions).
  - Entry animations are removed (rule above). The comparator ignores anti-aliased pixels, so before the rule only the mobile light shared meeting page showed it, one or two pixels in some runs; the rule re-rendered 684 earlier screenshots with no visible change.
- **Data changes on earlier screens.** Earlier fixtures were recorded again: the seed now sets each account's sign-in time and registration minute explicitly, and the platform totals include the new personas and the admin spend. 40 earlier screenshots changed for data, all from the support unread badge in the desktop sidebar:
  - the administrator's count on every admin screen (`shell.admin`, AI models, LiveKit);
  - Max's count on `billing.subscription.max`.
- **Admin screens are ru only.** The draft's admin texts are not translated, so admin states are captured in Russian (inventory, «Findings», step 7).

### 3.6 Recording from the draft backend

Fixtures come from the draft backend running locally with seeded test data, as the prompt requires. Built in step 2; the operating manual is [parity/recording/README.md](../../../parity/recording/README.md).

- **Stack** (`parity/compose.yaml`, profile `recording`):
  - the draft API built from the draft's own `requirements.txt` on Python 3.12 — it is the reference, not v2 code;
  - PostgreSQL 18 with pgvector and Redis 7.4.6, the versions the draft runs in production;
  - all of it on the `internal` network `draft`, with no route out and no published ports.
- **Isolation from production.**
  - The draft reads `.env` from its working directory, so it runs from a `git archive` export of tracked files, never from `/root/whisperer/backend`.
  - Every variable is passed explicitly, and provider keys are empty.
  - Verified: no `.env` in the export, and no outbound connection succeeds from the API.
- **Time.** The API runs under libfaketime with its wall clock stopped at the parity clock (from step 7; monotonic time stays real, so timers and time-outs run). Server-side "days left", "today" and windows such as "the last 10 minutes" or "the last 30 days" match the frozen browser whenever in the run a visit is recorded. Seeds write explicit timestamps. "Now" values and per-request tokens, ids and PKCE values are normalized by declared rules.
- **State per run.** A template database holds the migrated, seeded draft. Every run copies it, empties Redis and restarts the API. A visit that changes data uses its own persona.
- **Seeds.** Ten personas cover the tariffs, tour states, quota exhaustion, a saved card with payment history, a referrer, an administrator and a blocked account. They are created through the draft's own service registration, then adjusted through its ORM. Later steps add personas and data for their features the same way: through the ORM where the draft produces the data with AI or external services (transcripts, notes, mind maps).
- **Recorder.**
  - The draft frontend runs against the live draft API, with the persona signed in like a returning user. Every `/v1` exchange is captured.
  - The visitor's country goes in `CF-IPCountry` (default `RU`): currency, prices and the sign-in buttons depend on it.
  - Third-party sign-in SDKs get stubs, so they neither render nor raise the error toast a blocked script causes.
  - A visit fails when its marker is missing or an unexpected error toast appears.
  - Two runs give byte-identical fixtures.
- **Synthetic data.** What the local stack cannot produce is an override in the harness's state definitions, marked synthetic with a reason. Examples: a 429 from the rate limiter, a failed captcha, the OpenRouter balance, LiveKit health, connector catalogs, weather in the ticker. Overrides are validated against the draft's OpenAPI (D1).

### 3.7 Commands

Run from `parity/`; screenshots are taken inside the container. A slice selects its states with `--grep` on the state id.

| Command | What it does |
|---|---|
| `npm run baseline -- [--grep <prefix>]` | renders the draft, uploads the images to the S3 bucket and rewrites `baseline/manifest.json` |
| `npm run verify -- [--grep <prefix>]` | renders the draft again and compares with zero tolerance (definition of done: two runs, no differences) |
| `npm run compare -- --grep "meetings\."` | renders v2 and compares with the parity tolerance; HTML report with expected, actual and diff per state and cell |
| `npm run record -- --grep <prefix>` | re-records fixtures from the local draft stack |

Parity tolerance: per-pixel colour threshold 0.1 and at most 0.1 % of pixels per screenshot, overridable per state with a reason.

### 3.8 What the harness requires from v2

These follow from the goal "a user notices no difference" and are what lets one state definition drive both frontends. F2 and the slices keep them:

- **Base path.** The SPA is served under `/app/`, and the same paths and query parameters address the same screens.
- **Persisted client state.** `wh-auth` (`{state:{csrfToken,user},version:0}`), `wh.theme`, `wh.lang`, `wh.appearance`. A user signed in before the cutover stays signed in with the same theme and language. The harness seeds the same keys.
- **API.** The same `/v1` HTTP, SSE and WebSocket contract (D1). Fonts are served at `/fonts/`.
- **Randomness.** Random choices visible on screen go through `Math.random`, so the seed applies.
- **Selectors.** The texts, `aria-label`s, roles and `data-onboarding` anchors used as markers and interactions stay.
- **Motion.** v2 honours `prefers-reduced-motion` where the draft does. If a toast closes on another animation than `toast-bar`, its selector joins `PERSISTENT_ANIMATIONS`.

### 3.9 CI

D2 adds a `parity` job: `npm ci`, type check, and unit tests of the harness: state registry, synthetic responses against the draft OpenAPI, replay matching, normalization, matrix, manifest, translation texts. The job also runs shellcheck on the scripts and validates the Compose file. `scripts/ci/check_repository.py` applies the 200-line limit to TypeScript in `parity/` and the 300-line limit to Python there.

Screenshot runs on v2 are wired into CI by F2, when v2 has a frontend to compare.

## 4. Steps

Each step is one session, ends with checks and a report, and is committed after «Принято».

| Step | Content | Done when |
|---|---|---|
| 1 | Inventory, this plan, ADR 0003, status | inventory covers every route; plan and ADR approved |
| 2 | Recording stack: draft backend at the pinned commit with PostgreSQL and Redis, libfaketime, persona seeds, recorder, normalizer; fixtures for boot, shell, auth, account, billing, onboarding, referral, downloads, hotkeys | the stack starts with one command and records those fixtures; no production value is read |
| 3 | Harness core: targets, serving, strict replay, determinism, state DSL, matrix, `baseline` / `verify` / `compare`, report, unit tests, CI job, `parity/README.md`; the main states of step 2's features. Done: 44 states, 237 screenshots in S3 | `verify` shows 0 differences for those states |
| 3b | The remaining states of the shell, auth, account and billing group (inventory: shell-auth-account-billing.md), on the core of step 3:<br>• loading, empty and error variants through overrides;<br>• sign-in by social networks and consent;<br>• registration and reset validation;<br>• onboarding: tour steps on this group's routes, finish, checklist, launchers;<br>• billing flows: upgrade, promo, checkout, card sheet, renewal, payment issues;<br>• connection overlay, toasts, error boundary, command palette.<br>Tour steps 5–18 run on other features' routes and join the steps of those features. Every state of the group is screenshotted, captured inside another state, or left out with a reason (inventory, «Coverage in the screenshot matrix»). | `verify` shows 0 differences for those states |
| 4 | Meetings, calendar, context, knowledge, search (inventory: meetings-calendar-knowledge.md):<br>• seed persona `lead` with the whole workspace; ids shared by seed and visits in `recording/seed/ids.json`;<br>• library, import, meeting page (document, AI version, mind map, impact, share, menus, transcript), templates, integrations, shared page `/r/:token`;<br>• calendar views, event and stream dialogs, calendar integrations;<br>• context, knowledge base files, sources and connect flows; palette results.<br>Streams that send events over time join step 5. | same, for these states |
| 5 | Leo, prompts, models, MCP, hub (inventory: leo-prompts-models-mcp-hub.md):<br>• replay of open SSE streams and WebSocket frames on the state; the Leo conversation seeded in localStorage; the harness origin `http://parity.localhost` is a secure context, with a fake microphone;<br>• seed for `lead`: the Leo tab, MCP, hubs with boards and the Acme history of facts, prompts, skills, AI spend; two registry models from `admin`;<br>• Leo widget (panel, conversation content, streaming, actions, composer, mentions, voice, reminders), Leo cabinet tab, MCP tab and consent screen, prompts, skills, editor and test run, models, admin AI models, hubs;<br>• also the meeting AI version and mind map while their streams send text.<br>Done: 180 states, 288 screenshots | same, for these states |
| 6 | Rooms, streams, storage, tracker (inventory: rooms-streams-storage-tracker.md):<br>• fake LiveKit keys in the recording stack: room tokens and stream passes are signed locally; the harness closes the media server socket, so rooms stay «Не удалось подключиться» and everything drawn over HTTP is captured; SFU states excluded (decision 3);<br>• seed for `lead`: rooms with recordings and the LiveKit audit log, streams (live, ended, members only) with chat, hands and a waiting room, a file tree with share links, tracker boards with Jira links; personas `quota` and `overquota`;<br>• host and guest rooms, LiveKit admin, stream viewer and studio, files with every preview kind and the share dialog, public share pages, tracker projects, board and Jira.<br>Done: 168 states, 283 screenshots | same, for these states |
| 7 | Admin, product analytics, analytics, satisfaction, support (inventory: admin-analytics-support.md):<br>• the recording API's wall clock stops at the parity clock;<br>• seeds for every admin screen and a deterministic simulation of product analytics events; nine admin-only personas;<br>• dashboard, product analytics, users, tariffs, money, finance, security, support and broadcasts, app builds, client errors, platform prompts, affiliates, satisfaction and the survey card; the user's activity and support pages. Admin visits are read-only.<br>Done: 170 states, 227 screenshots | same, for these states |
| 8 | Locale sweep, full baseline in S3, full `verify`, status `done` | the prompt's definition of done |

## 5. Decisions

The owner approved this plan on 2026-10-01.

1. **Baseline storage — decided 2026-10-01: the production S3 bucket, prefix `parity-baseline/`.**
   - **Layout.** The PNGs live in object storage, not in git. Git holds a manifest: state, cell, SHA-256 and size of every baseline image. The harness downloads the images it needs by hash and checks them; `baseline` uploads new images and rewrites the manifest.
   - **Exception.** The owner allowed the production bucket and its credentials from `backend/.env`. This is an exception to REWRITE_PLAN §2 for this prefix only. The prefix is deleted when the rewrite is finished.
   - **Credentials.** The harness reads them from `PARITY_S3_*` environment variables; it never parses `backend/.env` itself. In CI they come from repository secrets that the owner adds.
   - **Prefix guard.** The harness refuses any object key outside `parity-baseline/`, and only `baseline` writes. Nothing else in the bucket is read, listed or deleted.
   - **Migration.** The bucket becomes the Russian home's bucket ([ADR 0006](../../adr/0006-draft-bucket-becomes-russian-home-bucket.md)), so M1 skips this prefix and M2 removes it.
2. **Matrix depth — decided 2026-10-01.** Main states get all 8 cells; small variants get one cell: `ru`, desktop, light. The rule is in §3.4. The owner's decision narrows the prompt's "`ru` and `en` for every state".
3. **SFU-dependent states — decided 2026-10-01: outside the matrix.**
   - Live participant tiles, the live whiteboard and stage video are not screenshotted, because WebRTC media cannot be recorded and replayed deterministically.
   - They are checked by hand on the staging domain.
   - Everything those pages render over HTTP is covered.
4. **Draft defects visible on screen — decided 2026-10-01: v2 fixes them; they stay out of the baseline.**
   - Example: the payment-return toasts show raw translation keys («cab.paySuccess» and the rest); v2 shows the translated texts.
   - The inventory marks such a state as a defect and leaves it out of the baseline; the slice that owns the screen checks the corrected behaviour with its own tests.

## 6. Risks

| Risk | Mitigation |
|---|---|
| The draft API needs more services at startup than PostgreSQL and Redis | resolved in step 2: NATS and Temporal are optional for the draft API; it starts with PostgreSQL and Redis only |
| Production enables a different set of social sign-in providers than the recording stack | resolved 2026-10-01: the owner confirmed that production enables all four — Yandex and VK for Russia and the Russian language, Google and GitHub for everyone else — as the recording stack does |
| A state needs a combination of requests that the draft API cannot produce | found in step 3b: hotkeys are never saved (the API caps the map at 16 actions, the page sends 22). Such states are marked unreachable in the inventory and stay out of the baseline |
| A draft defect would become a baseline that v2 must repeat | resolved 2026-10-01 (decision 4): defects stay out of the baseline, and v2 fixes them |
| A screen depends on time in a way libfaketime does not cover | the normalizer rule set is per field and reviewed in the recording report |
| Semgrep `p/default` flags token-like strings in fixtures | fixtures use fake values that do not look like JWTs or keys |
| v2 renders the same design with a newer Tailwind or React and differs by a few pixels | per-state tolerance with a written reason; never a global increase |
| The production bucket key sits on a development host and in CI secrets | the prefix guard above; the key is used only by `baseline` (write) and `verify` / `compare` (read); the owner can swap in a key limited to the prefix at any time without code changes |
| Full runs are too slow for every push | slices run their own prefix; F2 decides sharding and the schedule for full runs |
