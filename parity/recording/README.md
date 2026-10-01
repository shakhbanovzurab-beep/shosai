# Recording fixtures from the draft

The parity harness renders the draft and v2 from the same API data. That data is recorded here: the draft's own frontend talks to the draft's own backend, running locally with seeded test data, and every `/v1` response it receives becomes a fixture in [`../fixtures/`](../fixtures/). Plan: [D2 §3.6](../../docs/plan/packages/D2-visual-parity.md).

## One command

```bash
cd parity
npm ci                       # once
bash recording/record.sh     # all visits
bash recording/record.sh --grep "billing/"   # a subset, by visit id
```

The command:
1. exports the draft at the commit pinned in [`../parity.config.json`](../parity.config.json) with `git archive` (the draft's working tree is never touched) and builds its frontend in the harness container;
2. builds the draft API image and starts its PostgreSQL and Redis;
3. creates the template database once: the draft's migrations and the seed in [`seed/`](seed/). The template is recreated whenever the seed, the API Dockerfile or the pinned commit changes;
4. copies the template into a fresh working database, empties Redis and restarts the API, so every run starts from the same state;
5. checks that the API sees the parity clock, then runs [`../src/recording/record.spec.ts`](../src/recording/record.spec.ts).

Two runs produce byte-identical fixtures. Check this after any change to the seed, the visits or the normalizer.

## Isolation from production

- The draft API runs from the export, which holds tracked files only. The draft's `backend/.env` does not exist there, and the draft reads `.env` only from its working directory.
- Every setting is passed explicitly in [`../compose.yaml`](../compose.yaml). AI, payment, mail and storage credentials are empty.
- The stack lives on the Compose network `draft`, which is `internal`: no route to the internet. Databases publish no ports.

## Environment of the draft API

| Setting | Value | Why |
|---|---|---|
| Image | the draft's `requirements.txt` on `python:3.12-slim`, pinned by digest | the draft is the reference; its versions are not v2's |
| PostgreSQL, Redis | 18 with pgvector, 7.4.6 | what the draft runs in production |
| libfaketime | `@2026-07-17 12:00:00` (from `parity.config.json`) | "days left", "today" and creation times do not depend on the day of recording |
| `RATELIMIT_ENABLED` | `false` | the recorder signs in once per visit from one address; the limit of 5 per minute on login and refresh would stop it |
| `TRUST_CF_IPCOUNTRY` | `true` | the visitor's country, sent by the recorder as `CF-IPCountry`, decides currency, prices and auto-renewal, as behind Cloudflare in production |
| Social sign-in | Yandex, VK, Google and GitHub enabled with fake client ids | the buttons render; no request reaches the providers |
| `SCHEDULERS_ENABLED` | `false` | no background loops between visits |

## Personas

Defined in [`seed/personas.py`](seed/personas.py); the password of every persona is `parity-password-1`.

| Persona | State |
|---|---|
| `free` | Free tariff, tour completed, 12 of 60 minutes used, invited `start` and `pro` |
| `new` | registered at the parity clock, tour not started |
| `tour` | tour active at step `map` |
| `exhausted` | Free tariff, all 60 minutes used |
| `start`, `pro`, `max` | paid tariffs; `pro` has a saved card, auto-renewal and payment history |
| `admin` | administrator |
| `banned` | blocked account |
| `editor` | used only by visits that change the profile |

A visit that changes data uses a persona no other visit uses: the draft API caches per user in memory, and a change must not leak into another visit of the same run. The recorder enforces this.

## Visits

A visit ([`../src/recording/visits/`](../src/recording/visits/)) is a persona, a URL, optional actions, a marker that exists only on the intended screen, and optionally a country and languages.

- **Languages.** A visit is recorded in each of its languages, `ru` and `en` by default, into `fixtures/<visit>.<language>.json`. The page language and the persona's profile language are both the recording language: the draft switches the interface to the profile language, so the recorder sets it in `wh-auth` and in every `/v1/auth/me` response. A visit that changes data either uses language-specific data (`unverified-ru@…`, `unverified-en@…`) or records in one language.
- **Texts.** Markers and actions take texts from the draft's translation catalogs by key, `t("auth:titleLogin")`, so the same visit works in any language.

The recorder:

- signs the persona in through the API and puts its cookies and `wh-auth` into the browser, so the page boots like a returning user;
- proxies `/v1` to the draft API and logs every exchange;
- answers the third-party sign-in SDKs with stubs ([`../src/serve/third-party.ts`](../src/serve/third-party.ts)) and blocks every other external host;
- rejects the visit if the marker is missing, or if an error toast appears that the visit does not expect;
- waits until the API has been quiet for one second, normalizes the exchanges ([`../src/recording/normalize.ts`](../src/recording/normalize.ts)) and writes the fixture.

To add a visit, add it to the list of its feature group, record with `--grep <id>`, and run the whole recording twice to confirm the fixtures do not change.

## What cannot be recorded

Some responses cannot come from the local stack, for example a 429 from the rate limiter or a failed captcha check. They are overrides in the state definitions of the harness, marked synthetic with a reason. They are not separate fixtures.
