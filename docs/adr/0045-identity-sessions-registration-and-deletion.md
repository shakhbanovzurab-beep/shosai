# ADR 0045 — Identity: sessions, registration across homes, consent and deletion

- **Status:** accepted by the owner on 2026-10-14 (identity slice plan, decisions ID-D1, ID-D2, ID-D4 … ID-D10).
- **Package:** `identity`; the slice settings and ports between slices are platform mechanisms built in its first step; every slice that serves a person's data to others honours the deletion window; M1 (consent of migrated accounts) and M2 (desktop client release).
- **Context documents:** [identity plan](../plan/slices/identity.md); [ARCHITECTURE.md](../design/ARCHITECTURE.md) fr-6 … fr-8, nfr-4, nfr-12 … nfr-14, §6, §8.1, §10, §13.2, §14 rule 7, §15, §18; [DATA_MAPPING.md](../plan/DATA_MAPPING.md) §5.1, R4 … R6; [ADR 0039](0039-one-account-per-person-with-workspaces.md); [ADR 0034](0034-platform-services-in-core.md) and [ADR 0029](0029-leo-tools-owned-by-domain-slices.md) (contracts in core, runtime in a slice).

## Context

- Shosai's first slice must sign people in on the web and on the desktop in the home of their country, keep the shipped macOS and Windows 1.4.5 clients signed in across the cutover (R6), and give every other slice an authenticated person.
- Several choices were open or contradicted by the draft:
  - the captcha provider (the architecture named Yandex SmartCaptcha; the draft uses Cloudflare Turnstile);
  - cross-border consent, which the draft never collected;
  - where a pending registration lives, since Valkey is in the EU;
  - how a ban reaches a session without a database read per request;
  - when a deleted account's data disappears;
  - the desktop URL scheme after the rebrand.

## Decision

1. **Tokens stay compatible with the draft.**
   - Claims and lifetimes:
     - HS256 with the draft's key and the claims `sub typ tv iat exp`, plus `fid jti` on refresh tokens.
     - Access tokens live 30 min. Refresh tokens live 7 days, sliding, rotated per family with a 10 s grace for the previous `jti`. Reuse revokes the family.
   - New in v2:
     - a `kid` header (none = the draft's key) and a `home` claim;
     - no company claim (§15 amended, ID-D9);
     - `jti` stored as SHA-256.
   - Cookies, CSRF and errors:
     - The cookie names `meetassist_refresh` and `meetassist_csrf` and the `X-CSRF-Token` rule are the native contract.
     - The CSRF value is not rotated by refresh.
     - The draft's `detail` strings are kept on the native routes.
2. **One authenticator for HTTP and WebSocket, with no database read per request** (ID-D6).
   - A ban, freeze, deletion request, password change, "sign out everywhere" or transfer writes an account-state marker in Valkey for the access-token lifetime.
   - Without Valkey within 20 ms, a request passes on the signature alone. Refresh always reads the home.
3. **Registration keeps personal data in the chosen home.**
   - A pending registration (email, name, password hash, code) is a row in the home database of the country the person chose. 152-FZ requires Russian users' data to be recorded in Russia first, and nfr-4 allows only the email HMAC, ids and the home outside the home.
   - Its routing (`email_hmac`, registration id, home) lives in the EU Valkey with the same 15-minute TTL.
   - Every registration has its own id, and verification needs (id, code). The directory is claimed at verification, so the first verification wins and a second registration cannot take over the first.
4. **Cloudflare Turnstile is the only captcha** (owner; §18 amended).
   - It is shown always on registration and on the password-reset request. On sign-in it is shown only after 3 failures in 15 min from an address or for an account, for every client; no request header exempts a client (ID-D1).
   - The server check fails closed.
5. **Cross-border consent (nfr-14)** (ID-D2).
   - A Russian-home account cannot be created without a separate, versioned consent, stored in an append-only consent journal.
   - Migrated accounts: a lawyer decides whether the personal-data consent of 2026-07-10 covers the transfer. If it does not, the cabinet asks once at the next sign-in.
   - Before a withdrawal takes effect, the person is told explicitly what stops, meeting transcription included, and confirms. The API refuses a withdrawal without that confirmation.
6. **Deletion has a 7-day window** (ID-D5).
   - **Confirmation:** the re-typed email and a session younger than 15 minutes.
   - **At once:**
     - every session ends and sign-in no longer opens the account;
     - the person's data is served to nobody: shared items, public links, workspace views, search, Leo and background work;
     - an email names the date of erasure;
     - the email address stays taken.
   - **Within 7 days:** signing in cancels the deletion and restores everything unchanged.
   - **After 7 days:** the deletion saga erases every slice's data through the registry and frees the email. `users` is anonymised last, because money rows reference it for 5 years.
   - Events: `identity.account.deletion_scheduled`, `.deletion_cancelled`, `.deleted`, with ids only.
7. **The export and deletion registry is a core contract** (`core/account_data`), because core's own tables hold personal data. It covers tables, object prefixes and external grants. Slices and core declare their parts; identity runs export, deletion and transfer over it. A metadata test fails on any uncovered table with a `user_id`.
8. **Avatars belong to identity** (ID-D4).
   - One object per account in the home's bucket. The signature is checked; nothing counts against the storage quota.
   - Served by a 15-minute presigned URL.
9. **Desktop browser sign-in redirects only to `shosai://auth`** (ID-D10).
   - The connect page asks for one confirmation click first (ID-D7).
   - A code issued with a PKCE challenge requires its verifier.
   - The macOS and Windows clients move to `shosai://` in a later release. Until then the shipped 1.4.5 builds cannot finish a browser sign-in on v2, which is an exception to nfr-12; their password sign-in keeps working. That release is a prerequisite of M2.
10. **Social sign-in:** Yandex and VK for Russia and unknown countries, Google and GitHub elsewhere, never both sets, decided on the server (406-FZ); no Apple (ID-D8).
    - A provider's email links to an existing account only when that provider proves verification.
11. **Slice settings and ports between slices.**
    - **Settings:** a slice declares its own settings sections.
    - **Ports:** it publishes services through port types in its `contracts.py` (`FeatureParts.provides`), resolved after every slice is built. Composition refuses to start on a missing or doubled binding.
    - **Use in identity:** other slices use the authenticator, operator checks and consent reads through these ports. Their parts of the native `GET /v1/auth/me` (billing, meetings, memory, agent) are multi-port contributions with the draft's defaults until those slices ship.

## Alternatives

- **New signing keys for v2.** Rejected: every user and desktop client would be signed out at cutover (R6).
- **Pending registrations in Valkey, as the draft did.** Rejected: personal data of Russian users would be recorded first outside Russia.
- **Yandex SmartCaptcha (the architecture's earlier choice).** Rejected by the owner. A person whose network blocks Cloudflare cannot register; the cabinet says so instead of locking the form silently.
- **Immediate deletion.** Rejected by the owner: no undo for a mistaken or coerced deletion.
- **Keeping `whisperer://` beside `shosai://` for the shipped builds.** Rejected by the owner: one scheme, and the clients are updated before cutover.
- **A database read per request for account state.** Rejected: 4 × 45 ms for every Russian request.

## Consequences

- ARCHITECTURE §8.1 (Account), §15 and §18 are amended; §16.4 gains the invariant monitor "directory entries without an account in their home".
- Every slice that serves a person's data to others subscribes to the deletion events and hides that data while deletion is scheduled; the registry test makes each slice declare its tables, prefixes and grants.
- Billing pauses renewals while deletion is scheduled.
- A Valkey outage widens the revocation window to the access-token lifetime (≤ 30 min).
- M1 depends on the lawyer's answer about migrated consent; M2 depends on the desktop release with `shosai://`.

## Revisit when

- The lawyer rules on migrated consent, or the consent text changes (a new version, asked again).
- Valkey outages become frequent enough that the revocation window matters → read account state from the home on refresh-sensitive routes.
- The 1.4.x builds are gone from the release statistics → the nfr-12 exception closes.
