# identity

One sign-in for the web and the desktop in the person's data home; profile and privacy; export and deletion of everything; operator accounts. Plan: [docs/plan/slices/identity.md](../../../../../docs/plan/slices/identity.md); decisions: [ADR 0045](../../../../../docs/adr/0045-identity-sessions-registration-and-deletion.md), [ADR 0046](../../../../../docs/adr/0046-platform-languages-follow-the-cabinet.md).

## Public surface

`contracts.py` is the only module other slices import:

- `Principal` and its tenancy scope;
- `OperatorRole`;
- the port keys `AUTHENTICATOR`, `CONSENT_READER` and `ACCOUNT_PROFILE_READER`, with their protocols;
- the events `identity.account.*` and `identity.sessions.revoked`, which carry ids only.

identity binds each port in the step of the plan that builds it.

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
- `module.py` — the `FeatureModule` listed in `composition/features.py`.
