# identity

One sign-in for the web and the desktop in the person's data home; profile and privacy; export and deletion of everything; the one admin's sign-in. Plan: [docs/plan/slices/identity.md](../../../../../docs/plan/slices/identity.md); decisions: [ADR 0045](../../../../../docs/adr/0045-identity-sessions-registration-and-deletion.md), [ADR 0046](../../../../../docs/adr/0046-platform-languages-follow-the-cabinet.md), [ADR 0048](../../../../../docs/adr/0048-web-sign-in-by-email-code.md), [ADR 0049](../../../../../docs/adr/0049-one-admin-signed-in-by-env-credentials.md).

## Public surface

`contracts.py` is the only module other slices import:

- `Principal` and its tenancy scope;
- the port keys `AUTHENTICATOR`, `CONSENT_READER`, `ACCOUNT_PROFILE_READER` and `ADMIN_GATE`, with their protocols;
- `require_admin(ports)`, the dependency of every `/v1/admin/*` route;
- the events `identity.account.*` and `identity.sessions.revoked`, which carry ids only.

identity binds each port in the step of the plan that builds it.

## Sign-in without a password

The cabinet signs in by an emailed code (`/v1/auth/email/*`, ADR 0048) or through a provider (`/v1/auth/social/*`). Both hand a new person a consent ticket that `POST /v1/auth/social/register` turns into an account in the home of the country they confirm. The code's challenge is sealed for the browser (the address travels inside, encrypted); Valkey keeps only the code's hash and the counters. The mail to an address without an account is written in the visitor's home: Russia, an unknown country or a Russian interface give the Russian home. The password routes stay for the shipped desktop clients.

## Export and deletion

identity runs the account data registry (`core/account_data`). Every owner that erases something binds one handler to `core.account_data_handlers`; composition refuses to start otherwise. `POST /v1/me/deletion` hides the account for 7 days, and a sign-in in that window cancels it. After the window, the `identity.erase_due` sweep starts the saga, and `identity.erase_account` runs the handlers with identity's last, journalled in `account_deletions`. After the last handler every owner reads its part again (`remains`); anything left increments `shosai_identity_erasure_leftovers_total` and is logged by id, and the `ErasureLeftovers` monitor pages (nfr-13). An access token is refused by an account marker only when the token is not newer than the marker.

`POST /v1/me/exports` queues an archive; the `identity.export_due` sweep and `identity.make_export` stream every handler's files into one ZIP in the home's bucket under `exports/<user_id>/`, kept 7 days.

## Invariant monitors

Two monitors of §16.4 are declared on the module (`objectives.py`) and rendered with `--update-rules`; their runbook sections are in `docs/runbooks/alerts.md`. `DirectoryEntryWithoutAccount` (inv-1): the hourly `identity.check_directory` (EU, after settling the stale claims) looks up every directory entry older than 10 minutes in its home and sets `shosai_identity_directory_orphans{home}`. `ErasureLeftovers` (nfr-13): the check after erasure above.

## Transfer between homes

The admin moves an account to the other home with `POST /v1/admin/users/{id}/transfers` once `IDENTITY_TRANSFERS_ALLOWED` is true (after the legal review, §22). The saga `TransferSaga` journals its steps in `home_transfers` of the source home: freeze, copy every owner's part, verify the manifests of both homes, switch the EU directory, bump the token version in the target, purge the source. A cancel works until the switch. Rows kept by law stay in the home that wrote them.

## The admin

Shosai has one admin, and the admin is not a person's account (ADR 0049). `POST /v1/admin/session` checks the login and the bcrypt hash from `IDENTITY_ADMIN_USERNAME` and `IDENTITY_ADMIN_PASSWORD_HASH` — a wrong login still spends a bcrypt check — with attempts limited per address and for the login as a whole. It sets the cookie `shosai_admin` (HttpOnly, SameSite=Strict, path `/v1/admin`, 8 hours): a signed nonce whose hash Valkey keeps, so `DELETE /v1/admin/session` ends the session at once. `require_admin` checks it on every admin route. `shosai identity admin-password-hash` prints the hash of a password typed without echo.

The admin finds accounts at `/v1/admin/users` and acts on them through `AccountStates`, the one place that blocks and unblocks: the state, the token version, the sessions, the events and the audit event change in one home transaction, and the Valkey marker then refuses live tokens with the native 403. Each action writes `identity.operator.acted` with no operator id, and its EU delivery appends one row to `operator_audit_events`, which the application can never update or delete. Other slices record the admin's actions on a person's data through the `identity.operator_audit` port (`OperatorJournal`), in their own transaction of the person's home: files' support list and restore (`files_listed`, `file_restored`), with the touched item's id in `subject_id` (revision `d8b3e6a0f914`), and meetings' (`meetings_listed`, `meeting_restored`, revision `a7c3e9f2b158`).

## Layout

- `domain/` — pure rules:
  - normalised addresses and the directory HMAC;
  - the home of a country;
  - password rules and the 72-byte bcrypt input;
  - account states and their sign-in refusals;
  - the claims of draft-compatible tokens.
- `infrastructure/`:
  - `token_codec.py` — HS256 with a `kid` ring; a token without `kid` is checked with the draft key `d`;
  - `password_hasher.py` — bcrypt in a bounded thread pool, with a decoy check for unknown addresses.
- `settings.py` — `IDENTITY_TOKEN_KEYS`, `IDENTITY_DIRECTORY_HMAC_KEY`, `IDENTITY_PASSWORD_HASH_ROUNDS`, documented in `.env.example` section 2, and the production check of their values.
- `module.py` — the `FeatureModule` listed in `composition/features.py`; `social_wiring.py` (social and email-code sign-in), `deletion_wiring.py`, `export_wiring.py`, `admin_wiring.py` and `transfer_wiring.py` build their parts of it.
