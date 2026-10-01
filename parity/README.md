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

1. **Record** the visits the screens need (persona, URL, actions, marker) in `src/recording/visits/`. Run `npm run record -- --grep <visit>`, then record everything twice to confirm the fixtures do not change.
2. **Define** each inventoried state in `src/states/<feature>.ts` and add the list to [`src/states/registry.ts`](src/states/registry.ts):
   - `fixture`: the visit that provides the data;
   - `scope`: `full` for main states, which get all 8 cells; `single` for small variants, which get one cell: ru, desktop, light;
   - `act`: the interaction;
   - `marker`: a selector that exists only in that state. Without the marker the state fails.
   - `overrides`: responses the recording stack cannot produce, such as an error status, a held request for loading, or a network failure. Each needs a reason, and each must exist in the draft's OpenAPI and match its schema. The unit tests check this.
3. **Texts** in markers and actions come from the draft's translation catalogs by key: `t("billing:cab.tariffs")`. Use literal keys, then run `npm run texts`.
4. **Baseline**: `npm run baseline -- --grep "<feature>\."`, then `npm run verify -- --grep "<feature>\."` must report no differences.
5. **Commit** the visits, fixtures, state definitions, `texts.json` and `baseline/manifest.json`. The images are already in S3.

## What makes a screenshot repeatable

Every state is rendered under the same conditions:
- the browser clock is frozen at the parity clock (`parity.config.json`), with time zone Europe/Moscow;
- `Math.random` is seeded;
- the system setting "reduce motion" is on;
- animations and transitions have zero duration from the first frame, except the animations in `PERSISTENT_ANIMATIONS` (`src/determinism/page-setup.ts`), which stop on their first frame because their end changes the screen (a toast closes when its bar ends);
- the pointer is parked at (0, 0), and service workers are blocked;
- external hosts are blocked; third-party sign-in SDKs and the captcha are stubs ([`src/serve/third-party.ts`](src/serve/third-party.ts));
- the screenshot waits for the marker, loaded fonts, and 500 ms without API requests and without DOM changes.

Values that follow real time, such as a "resend in 60 s" countdown, are masked per state, with a reason.

## What v2 must keep for the harness to work

These also follow from the goal that users notice no difference:

- **Base path and URLs.** The SPA lives under `/app/`, and the same paths and query parameters address the same screens.
- **Persisted client state.** `wh-auth` (`{state:{csrfToken,user},version:0}`), `wh.theme`, `wh.lang` and `wh.appearance` keep their meaning. Users stay signed in across the cutover, and the harness seeds these keys.
- **API.** The same `/v1` contract (D1). Fonts are served at `/fonts/`.
- **Selectors used by states.** Texts from the draft catalogs, roles, `aria-label`s and `data-onboarding` anchors stay. The few draft class names in state definitions (`.onb-card`) are kept or the selector is replaced together with the state.
- **Motion.** v2 honours `prefers-reduced-motion` where the draft does. Random choices on screen use `Math.random`. If a toast closes on a different animation than `toast-bar`, its selector is added to `PERSISTENT_ANIMATIONS`.

## Baseline storage

Images live in the production S3 bucket under `parity-baseline/sha256/<sha256>.png`. The owner decided this; the prefix is deleted after the rewrite, and M1 skips it. Git holds [baseline/manifest.json](baseline/manifest.json): cell, state, hash and size of every image. The harness refuses any key outside the prefix and never lists or deletes anything.

Credentials come from `PARITY_S3_ENDPOINT`, `PARITY_S3_REGION`, `PARITY_S3_BUCKET`, `PARITY_S3_ACCESS_KEY_ID` and `PARITY_S3_SECRET_ACCESS_KEY`:
- `baseline` needs them;
- `verify` and `compare` need them only when the local copy in `.cache/baseline` does not match the manifest;
- in CI they are repository secrets.
