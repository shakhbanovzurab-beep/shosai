# ADR 0048 — The cabinet signs in by an emailed code, not a password

- **Status:** accepted by the owner on 2026-10-14 (web without passwords; consents asked once, only of a new person).
- **Package:** `identity` (steps 10b and 10c); the shipped native clients' contract is unchanged (nfr-12).
- **Context documents:** [ADR 0045](0045-identity-sessions-registration-and-deletion.md) (registration, consents, social sign-in); [contracts/README.md](../../contracts/README.md); [ARCHITECTURE.md](../design/ARCHITECTURE.md) nfr-4, nfr-14, §6.

## Context

- Step 10 shipped the draft's set of screens: sign-in by password, registration with a code, password reset, social sign-in.
- The owner wants one quiet screen: quick sign-in buttons, then "or use your email" → a one-time code. Russian visitors see Yandex and VK, everyone else Google and GitHub. The server already chooses that set by country and language (`visible_providers`, 406-FZ).
- 152-FZ needs a separate, explicit consent to personal data processing, and for an account in the Russian home a separate consent to cross-border transfer (ADR 0045 point 5). A "by continuing you agree" line covers the terms of use, not these consents.

## Decision

1. **The cabinet has no password field.** A person enters an email and receives a 6-digit code; the same code signs in a known person and starts the account of a new one. Registration, password reset and sign-in by password leave the cabinet's screens.
2. **The API keeps the password routes.** `POST /v1/auth/login`, `/register`, `/password/*` and the desktop routes stay for the shipped native clients; `/app/reset` stays reachable for links already sent.
3. **New routes** (identity step 10b):
   - `POST /v1/auth/email/start` `{email, language, next?, captcha_token?}` → `202 {challenge_id, resend_after_seconds}`. The answer is the same whether or not an account exists. The challenge (email HMAC, code hash, attempts, home if known) lives in Valkey for 15 minutes; the address itself is only used to send the mail. A captcha is asked after failures, as for sign-in.
   - `POST /v1/auth/email/verify` `{challenge_id, code}` → a session for a known person, or a consent ticket for a new one (the encrypted ticket of social sign-in, with the method `email`). Five wrong codes end the challenge.
   - `POST /v1/auth/email/resend` `{challenge_id}`, with the same pacing as the registration code.
   - A new person finishes through the existing `POST /v1/auth/social/register` path, generalised to any consent ticket: country, language and the consents create the account in its home.
4. **Consents once, only for a new person.** After the code or after a provider, a person without an account sees one step: country, the personal-data consent with links to the documents, the cross-border consent when the country is Russia, and the optional newsletter. A known person goes straight in. The screen's footer says that continuing accepts the terms of use and the privacy policy.

## Consequences

- One screen and one path for everyone; nobody keeps or resets a password on the web.
- Email delivery becomes part of every web sign-in: the mail's latency and deliverability are watched (F5), and the code mail goes through the account mailbox.
- A person who used a password before keeps it for the desktop clients until they are updated; on the web the code replaces it.
- Contract tests of the native routes (step 13) are unaffected.

## Revisit when

- Passkeys are added (a second quiet method next to the code).
- The native clients move to the browser sign-in only; then the password routes can be retired.
