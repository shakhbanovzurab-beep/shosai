# identity

One sign-in for the web and the desktop in the person's data home; profile and privacy; export and deletion of everything; operator accounts. Plan: [docs/plan/slices/identity.md](../../../../../docs/plan/slices/identity.md); decisions: [ADR 0045](../../../../../docs/adr/0045-identity-sessions-registration-and-deletion.md), [ADR 0046](../../../../../docs/adr/0046-platform-languages-follow-the-cabinet.md).

## Public surface

`contracts.py` is the only module other slices import:

- `Principal` and its tenancy scope;
- `OperatorRole`;
- the port keys `AUTHENTICATOR`, `CONSENT_READER`, `ACCOUNT_PROFILE_READER` and `OPERATOR_ROLES`, with their protocols;
- `require_operator(ports, *roles)`, the dependency of every `/v1/admin/*` route;
- the events `identity.account.*` and `identity.sessions.revoked`, which carry ids only.

identity binds each port in the step of the plan that builds it.

## Export and deletion

identity runs the account data registry (`core/account_data`). Every owner that erases something binds one handler to `core.account_data_handlers`; composition refuses to start otherwise. `POST /v1/me/deletion` hides the account for 7 days, and a sign-in in that window cancels it. After the window, the `identity.erase_due` sweep starts the saga, and `identity.erase_account` runs the handlers with identity's last, journalled in `account_deletions`. An access token is refused by an account marker only when the token is not newer than the marker.

`POST /v1/me/exports` queues an archive; the `identity.export_due` sweep and `identity.make_export` stream every handler's files into one ZIP in the home's bucket under `exports/<user_id>/`, kept 7 days.

## Transfer between homes

An operator moves an account to the other home with `POST /v1/admin/users/{id}/transfers` once `IDENTITY_TRANSFERS_ALLOWED` is true (after the legal review, §22). The saga `TransferSaga` journals its steps in `home_transfers` of the source home: freeze, copy every owner's part, verify the manifests of both homes, switch the EU directory, bump the token version in the target, purge the source. A cancel works until the switch. Rows kept by law stay in the home that wrote them.

## Operators

Roles live in the person's home and are read on every admin request. An owner changes them under one platform-wide lock, and the last owner keeps the role. Each action writes `identity.operator.acted`, and its EU delivery appends one row to `operator_audit_events`, which the application can never update or delete. The first owner comes from `shosai identity grant-operator --email ADDRESS --role owner`.

Support finds accounts at `/v1/admin/users` and acts on them through `AccountStates`, the one place that blocks, unblocks and bans: the state, the token version, the sessions, the events and the audit event change in one home transaction, and the Valkey marker then refuses live tokens with the native 403.

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
- `module.py` — the `FeatureModule` listed in `composition/features.py`; `social_wiring.py`, `deletion_wiring.py`, `export_wiring.py`, `operator_wiring.py` and `transfer_wiring.py` build their parts of it.
