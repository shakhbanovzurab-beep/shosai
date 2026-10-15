# ADR 0048 — The cabinet signs in by an emailed code, not a password

- **Status:** accepted by the owner on 2026-10-14 (web without passwords; consents asked once, only of a new person; the home of the first mail by the visitor's country — the same day).
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
   - `POST /v1/auth/email/start` `{email, language, next?, captcha_token?}` → `202 {challenge, resend_after_seconds}`. The answer is the same whether or not an account exists. The challenge is sealed for the browser — a Fernet token carrying the address, the home of its mail, `next` and the language, valid 15 minutes — so no address waits in Valkey in the EU; Valkey keeps only the code's hash, the attempts and the resends under the hash of the challenge's nonce. A captcha is asked after failures, as for sign-in; five codes per address per hour.
   - `POST /v1/auth/email/verify` `{challenge, code}` → `{session}` for a known person (refresh cookie set, address marked verified), or `{consent_ticket}` for a new one — the encrypted consent ticket of social sign-in, carrying the proven address. Five wrong codes end the challenge (`code_locked`); a code works once.
   - `POST /v1/auth/email/resend` `{challenge}`, with the registration code's pacing: a minute apart, three at most.
   - A new person finishes through the existing `POST /v1/auth/social/register` path, generalised to any consent ticket: country, language and the consents create the account in its home.
4. **The home of the first mail.** The code mail to an address with an account is written in the account's home. To an address without one it is written before the person names a country, in the visitor's home: Russia, a country the edge did not name, or a Russian interface give the Russian home; any other country the EU home — the rule that already picks the providers' set (406-FZ). The account itself is created in the home of the country confirmed on the consent step.
5. **Consents once, only for a new person.** After the code or after a provider, a person without an account sees one step: country, the personal-data consent with links to the documents, the cross-border consent when the country is Russia, and the optional newsletter. A known person goes straight in. The screen's footer says that continuing accepts the terms of use and the privacy policy.

## Consequences

- One screen and one path for everyone; nobody keeps or resets a password on the web.
- Email delivery becomes part of every web sign-in: the mail's latency and deliverability are watched (F5), and the code mail goes through the account mailbox.
- A person who used a password before keeps it for the desktop clients until they are updated; on the web the code replaces it.
- Contract tests of the native routes (step 13) are unaffected.
- A Russian citizen abroad with a non-Russian interface gets the first code mail written in the EU home; the account itself still lives in the Russian home once they confirm Russia. The legal review of §22 covers this case.

## Revisit when

- Passkeys are added (a second quiet method next to the code).
- The native clients move to the browser sign-in only; then the password routes can be retired.
