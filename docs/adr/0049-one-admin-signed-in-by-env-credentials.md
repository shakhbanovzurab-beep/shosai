# ADR 0049 — One admin, signed in at a separate address with credentials from the environment

- **Status:** accepted by the owner on 2026-10-15 (one admin; a shared login and password from env; block and unblock only).
- **Package:** `identity` (steps 12a and 12b); supersedes the operator roles of identity step 8a (SM-12) and the ban action of step 8b.
- **Context documents:** [ADR 0045](0045-identity-sessions-registration-and-deletion.md); [ARCHITECTURE.md](../design/ARCHITECTURE.md) §7 (access), §16 (audit), nfr-17; [identity plan](../plan/slices/identity.md) steps 8a, 8b, 12.

## Context

- Step 8a gave operators roles held by their Shosai accounts (owner, support, finance, platform, releases, read-only), a CLI to grant the first owner, and an EU audit log keyed by the operator's account.
- The owner decided that Shosai has exactly one operator, the admin, and that the admin signs in at a separate address with a login and password kept in the environment — not with a person's account.
- Banning (closing an account for good, its address never registrable again) is not wanted: block and unblock are enough.

## Decision

1. **One admin, credentials in the environment.** `IDENTITY_ADMIN_USERNAME` and `IDENTITY_ADMIN_PASSWORD_HASH` (a bcrypt hash, printed by `shosai identity admin-password-hash`; the password itself never sits in a file). Production refuses to start without them.
2. **A separate address.** The cabinet's admin sign-in page lives at a path chosen at build time (`VITE_ADMIN_LOGIN_PATH`); the admin panel's routes are not linked from the user's cabinet.
3. **Its own session.** `POST /v1/admin/session` checks the credentials (rate-limited per address and for the login; a wrong attempt is logged, the password never) and sets the cookie `shosai_admin`: HttpOnly, Secure, SameSite=Strict, path `/v1/admin`, 8 hours. The cookie carries a nonce signed with a key derived from the token signing key; Valkey keeps the nonce's hash for the session's life, so `DELETE /v1/admin/session` ends it at once. `GET /v1/admin/session` tells the cabinet whether the admin is signed in.
4. **`require_admin` replaces `require_operator`.** Every `/v1/admin/*` route depends on it; it is unrelated to people's accounts and tokens.
5. **Block and unblock only.** The ban action, its route and its audit action go. Accounts already in the banned state (migrated from the draft) stay closed.
6. **The audit log stays.** Each action still writes one EU audit row; its operator is empty — the admin — with the action, the target and the time.
7. **Roles go.** The `operator_roles` table, the roles port, `Me.operator_roles`, the roles screens and `grant-operator` are removed; the operator directory planned for errors and support is not built.

## Consequences

- No one's personal account can reach the admin panel; a leaked user session gives no admin rights.
- The audit log cannot tell people apart behind the one admin login — accepted by the owner.
- Changing the admin password is an env change and a restart; every admin session ends with a key rotation or a Valkey flush.

## Revisit when

- A second person needs admin access, or an audit by person becomes a legal requirement.
