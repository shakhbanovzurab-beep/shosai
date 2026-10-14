# identity

One sign-in for the web and the desktop in the person's data home; profile and privacy; export and deletion of everything; operator accounts. Plan: [docs/plan/slices/identity.md](../../../../../docs/plan/slices/identity.md); decisions: [ADR 0045](../../../../../docs/adr/0045-identity-sessions-registration-and-deletion.md), [ADR 0046](../../../../../docs/adr/0046-platform-languages-follow-the-cabinet.md).

## Public surface

`contracts.py` is the only module other slices import:

- `Principal` and its tenancy scope;
- `OperatorRole`;
- the port keys `AUTHENTICATOR`, `CONSENT_READER` and `ACCOUNT_PROFILE_READER`, with their protocols;
- the events `identity.account.*` and `identity.sessions.revoked`, which carry ids only.

identity binds each port in the step of the plan that builds it.

## Deletion

identity runs the account data registry (`core/account_data`). Every owner that erases something binds one handler to `core.account_data_handlers`; composition refuses to start otherwise. `POST /v1/me/deletion` hides the account for 7 days, and a sign-in in that window cancels it. After the window, the `identity.erase_due` sweep starts the saga, and `identity.erase_account` runs the handlers with identity's last, journalled in `account_deletions`. An access token is refused by an account marker only when the token is not newer than the marker.

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
- `module.py` — the `FeatureModule` listed in `composition/features.py`; `social_wiring.py` and `deletion_wiring.py` build their parts of it.
