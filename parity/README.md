# Visual parity harness

Proves that v2 looks like the draft. Both frontends render the same recorded API data in the same pinned browser, and every screen state is compared pixel by pixel with the draft's baseline. Plan: [docs/plan/packages/D2-visual-parity.md](../docs/plan/packages/D2-visual-parity.md). Decision record: [ADR 0003](../docs/adr/0003-playwright-visual-parity-harness.md).

| Part | Where |
|---|---|
| What is checked: every draft route and state | [inventory/](inventory/README.md) |
| On which data: fixtures recorded from the draft API | [recording/](recording/README.md), [fixtures/](fixtures/) |
| State definitions | [src/states/](src/states/) |
| Baseline: a manifest in git, images in S3 | [baseline/manifest.json](baseline/manifest.json) |

## Run the comparison for a slice

```bash
cd parity
npm ci                                        # once
npm run compare -- --grep "billing\."         # v2 against the baseline, one slice
npx playwright show-report .cache/report      # expected, actual and diff per state and cell
```

`--grep` selects states by id. Ids follow the inventory: `<feature>.<screen>.<state>`. `compare` needs a built v2 frontend at the paths in [`parity.config.json`](parity.config.json) (`v2`). F2 sets them.

A screenshot passes when at most 0.1 % of its pixels differ by more than the colour threshold 0.1. A state can raise its own tolerance only with a written reason. The global tolerance is never raised.

## Commands

| Command | Target | What it does |
|---|---|---|
| `npm run compare -- [--grep …]` | v2 | Restores the baseline from the manifest, renders v2, compares with the parity tolerance. |
| `npm run verify -- [--grep …]` | draft | Renders the draft again and compares with zero tolerance. A pass proves that the screenshots reproduce. |
| `npm run baseline -- [--grep …]` | draft | Renders the draft, uploads new images to S3, updates `baseline/manifest.json`. |
| `npm run record -- [--grep …]` | draft API | Records fixtures from the local draft stack ([recording/README.md](recording/README.md)). |
| `npm test`, `npm run typecheck` | — | Unit tests and types; CI runs both. |
| `npm run texts` | — | Regenerates [`src/i18n/texts.json`](src/i18n/texts.json) from the draft's translation catalogs. |

Screenshots are taken only inside the pinned Playwright container ([`compose.yaml`](compose.yaml), service `harness`), so results are identical on every machine. `baseline`, `verify` and `record` export the draft at the pinned commit; they need the draft repository (`DRAFT_REPO`, default `/root/whisperer`). `compare` needs only this repository.

## Add the states of a slice

1. **Record** the visits the screens need (persona, URL, actions, marker) in `src/recording/visits/`. Run `npm run record -- --grep <visit>`, then record everything twice to confirm the fixtures do not change. A visit opens a known record through the ids in [`recording/seed/ids.json`](recording/seed/ids.json); the normalizer maps the ids in its URL to the same placeholders as in the requests. Data loaded on demand (a dialog, a tab) is in the fixture only if the visit opens it.
2. **Define** each inventoried state in `src/states/<feature>.ts` and add the list to [`src/states/registry.ts`](src/states/registry.ts):
   - `fixture`: the visit that provides the data;
   - `scope`: `full` for main states, which get all 8 cells; `single` for small variants, which get one cell: ru, desktop, light;
   - `sweep`: the state is also captured in the 14 other locales, desktop and mobile, light — the locale sweep, which catches layout breaks in long and right-to-left scripts. It is set on one text-dense screen, `meetings.library.populated`; its visit records in all 16 languages (`languages`), and the unit tests require a fixture in the language of every cell;
   - `act`: the interaction. It starts once the page has settled (fonts, API and DOM quiet), as a user who waits for the page: an action on a page still loading scrolls to its target in a layout that is about to change;
   - `marker`: a selector that exists only in that state. Without the marker the state fails.
   - `overrides`: responses the recording stack cannot produce, such as an error status, a held request for loading, or a network failure. Each needs a reason, and each must exist in the draft's OpenAPI and match its schema. The unit tests check this. Helpers are in [`src/states/overrides.ts`](src/states/overrides.ts):
     - a path may use `{param}` segments (`/v1/me/sessions/{id}/full`): ids in fixtures are placeholders, and an exact path wins over a template;
     - `respond` is one reply or a sequence: the n-th request gets the n-th reply, and the last repeats. A reply is a response, `"hold"` (no answer: loading), `"fail"` (network failure), `"recorded"` (the recorded answer), or `{ merge }` (the recorded answer with fields merged in, for variants of the same data such as "quota almost full");
     - `stream(...)` answers with a finished server-sent event stream; an event named `""` is a bare `data:` frame (the prompt test run, `[DONE]`);
     - `openStream(...)` sends its events and keeps the stream open: a reply still being written. A shim over `fetch` in the page serves it ([`src/determinism/open-streams.ts`](src/determinism/open-streams.ts)), because a response fulfilled by Playwright always ends.
     - `content(...)` answers with a file's text under its own type, `binary(...)` with bytes (`bodyEncoding: "base64"`): file previews, whose content the recording stand cannot read without S3. Sample documents are built in memory ([`src/samples/`](src/samples/));
     - a signed S3 URL in a synthetic `download-url` points at the stand-in object store `http://objects.parity.localhost` ([`src/serve/object-store.ts`](src/serve/object-store.ts)), which serves the sample image and PDF and answers 404 for anything else.
   - `sockets`: WebSocket frames for `/v1/ws/...` ([`src/replay/sockets.ts`](src/replay/sockets.ts)). `frames` go right after the page connects; `afterClient` goes after the page's first message, the way the voice server answers microphone audio. Without a script a `/v1/` socket stays silent and a socket to another host (the LiveKit media server) is closed; a script for `/rtc/v1` with no frames keeps the media server connecting.
   - `storage`: localStorage keys the frontend keeps in the browser, built from the fixture's user id: the Leo conversation (`agent-chat-v1:<user>`).
   - `session`: sessionStorage keys, such as a stream viewer's knock token.
   - `mediaAccess`: the browser's answer to the camera and microphone request — `"denied"` or `"pending"` (never answered) instead of the granted fake devices ([`src/determinism/media-access.ts`](src/determinism/media-access.ts)).
   - `mask`: regions drawn by real time or a live device, such as the fake camera's moving picture, with a reason.
   - `reveal`: the marker is below the edge of the screen; once the page has settled, the marker is scrolled to the centre of its scroll area (always the same position, whatever the action scrolled before) and the page settles again before the screenshot.
   - `keepPointer`: the state is a hover; the pointer stays where the action left it.
3. **Texts** in markers and actions come from the draft's translation catalogs by key: `t("billing:cab.tariffs")`. Use literal keys, then run `npm run texts`.
4. **Coverage**: a state of the inventory that is not screenshotted under its own id gets a row in its group's «Coverage in the screenshot matrix» section — captured inside another screenshot, or left out with a reason. `npm test` fails on a state with neither ([inventory/README.md](inventory/README.md)).
5. **Baseline**: `npm run baseline -- --grep "<feature>\."`, then `npm run verify -- --grep "<feature>\."` must report no differences.
6. **Commit** the visits, fixtures, state definitions, `texts.json` and `baseline/manifest.json`. The images are already in S3.

## What makes a screenshot repeatable

Every state is rendered under the same conditions:
- the browser clock is frozen at the parity clock (`parity.config.json`), with time zone Europe/Moscow;
- `Math.random` is seeded;
- the system setting "reduce motion" is on;
- animations and transitions have zero duration from the first frame, except the animations in `PERSISTENT_ANIMATIONS` (`src/determinism/page-setup.ts`), which stop on their first frame because their end changes the screen (a toast closes when its bar ends);
- entry animations in `ENTRY_ANIMATIONS` (the draft's `.rise`) are removed altogether: their last frame is the element's own style, and a filled zero-length animation of opacity and offset sometimes put the element on a composited layer, which moved its anti-aliasing by one colour level;
- the pointer is parked at (0, 0), and service workers are blocked;
- the origin `http://parity.localhost` is a secure context, as HTTPS is in production: the microphone, AudioWorklet and push exist. Chromium has a fake microphone and camera that grant themselves ([`src/determinism/browser-flags.ts`](src/determinism/browser-flags.ts)); recording uses the same browser;
- the Web Speech API is a silent recogniser: it starts and never hears anything, so nothing goes to the browser vendor's speech service;
- partial raster is off (`--disable-partial-raster`): a changed tile is redrawn whole. Otherwise an action on a drawn page redraws only changed rectangles, and anti-aliasing at their edges differs by a few brightness levels from run to run;
- text is always anti-aliased in greyscale (`--disable-lcd-text`). Chromium uses subpixel (LCD) text only outside composited layers, and blocks with an entry animation move in and out of a layer depending on timing, so the same text came out coloured in one run and grey in another;
- external hosts are blocked; third-party sign-in SDKs and the captcha are stubs ([`src/serve/third-party.ts`](src/serve/third-party.ts));
- the screenshot waits for the marker, loaded fonts, and 500 ms without API requests and without DOM changes.

Values that follow real time, such as a "resend in 60 s" countdown, are masked per state, with a reason.

## What v2 must keep for the harness to work

These also follow from the goal that users notice no difference:

- **Base path and URLs.** The SPA lives under `/app/`, and the same paths and query parameters address the same screens.
- **Persisted client state.** `wh-auth` (`{state:{csrfToken,user},version:0}`), `wh.theme`, `wh.lang` and `wh.appearance` keep their meaning. Users stay signed in across the cutover, and the harness seeds these keys. The Leo conversation stays in `agent-chat-v1:<user id>` and `agent-session-v1:<user id>` with the draft's message shape: users keep their thread, and Leo states seed it. A stream viewer's name stays in `wh.stream.name` and a pending knock in sessionStorage `wh.stream.knock.<invite>`.
- **API.** The same `/v1` contract (D1), including the SSE events of Leo and the prompt test run and the WebSocket frames of `/v1/ws/voice` and `/v1/ws/user`. File previews take text and documents from `content` and media from the URL that `download-url` returns. Fonts are served at `/fonts/`.
- **Selectors used by states.** Texts from the draft catalogs, roles, `aria-label`s and `data-onboarding` anchors stay. The few draft class names in state definitions (`.onb-card`) are kept or the selector is replaced together with the state.
- **Motion.** v2 honours `prefers-reduced-motion` where the draft does. Random choices on screen use `Math.random`. If a toast closes on a different animation than `toast-bar`, its selector is added to `PERSISTENT_ANIMATIONS`. If v2 names its entry animation differently from `.rise`, its selector is added to `ENTRY_ANIMATIONS`.

## Baseline storage

Images live in the production S3 bucket under `parity-baseline/sha256/<sha256>.png`. The owner decided this; the prefix is deleted after the rewrite, and M1 skips it. Git holds [baseline/manifest.json](baseline/manifest.json): cell, state, hash and size of every image. The harness refuses any key outside the prefix and never lists or deletes anything.

Credentials come from `PARITY_S3_ENDPOINT`, `PARITY_S3_REGION`, `PARITY_S3_BUCKET`, `PARITY_S3_ACCESS_KEY_ID` and `PARITY_S3_SECRET_ACCESS_KEY`:
- `baseline` needs them;
- `verify` and `compare` need them only when the local copy in `.cache/baseline` does not match the manifest;
- in CI they are repository secrets.
