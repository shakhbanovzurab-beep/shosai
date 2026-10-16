# ADR 0051 — New users reach the owner in Telegram, enriched by Clay

- **Status:** accepted by the owner on 2026-10-16. **The legal review is deferred by the owner** (see Consequences).
- **Packages:** a new slice `leads`; `identity` (the event it consumes); F6 (Telegram delivery is not F5's alerting path).
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §6 ("No other personal data outside a home"), §12, §22; [SLICE_MAP.md](../plan/SLICE_MAP.md) §4; [F5 plan](../plan/packages/F5-observability.md) F5-D5.

## Context

- The owner wants to see every new user at once — name, email, country — with what Clay (clay.com) can find about them, in Telegram, to work with them as leads.
- ARCHITECTURE §6 keeps personal data inside the user's home. F5-D5 keeps alerts free of personal data. Telegram and Clay are services outside both homes (Clay in the USA), so this is a cross-border transfer under 152-FZ and a third-party enrichment under GDPR Art. 14.
- The owner decided to build it now and to settle the legal side later.

## Decision

0. **Consent first.** Registration shows a separate, unticked checkbox: consent to share name, email and country with Shosai's sales tools (Clay, Telegram) to contact the person about Shosai. It is stored in `identity`'s `user_consents` with its text version and can be withdrawn in settings. The privacy policy names both services. **Only people who gave this consent are enriched and named in Telegram**; for the others the message carries country, sign-up source and the link to the account card, nothing else.
1. **A slice `leads`** owns the capability. It consumes `identity.account.registered` (ids only, §12), reads the profile through `identity`'s contract, sends the person to Clay for enrichment, stores the result in the user's home (`lead_enrichments`), and posts one message per new user to the owner's sales chat in Telegram: name, email, country, sign-up source and the enrichment, with a link to the account card in the admin panel.
2. **Separate from monitoring.** The sales chat and its bot are not F5's alert chat; F5-D5 stands: alerts carry no personal data.
3. **One switch, off by default.** `LEADS_ENABLED`, the Clay and Telegram credentials and the chat id come from the environment. With the switch off nothing leaves the home. Staging keeps it off unless the owner turns it on.
4. **Bounded copy.** Only the fields above leave the home. Clay receives email, name and country only. Enrichment results live in the home and are deleted with the account (they join `identity`'s deletion and export registry). Messages already posted in Telegram cannot be recalled; that is accepted.
5. **Idempotent and quiet.** One enrichment and one message per user (effect key `leads:<user_id>`), retried through the outbox; a Clay or Telegram failure never affects registration.

## Consequences

- **Remaining legal exposure, accepted by the owner until the review:** the Roskomnadzor notice of the cross-border transfer is not filed yet, and the consent text has not been checked by a lawyer. ARCHITECTURE §22 lists this item; the review settles both before launch to the public.
- ARCHITECTURE §6 gains one named exception pointing here.
- The slice is small (one consumer, one table, two adapters) and can be built right after `identity`.

## Revisit when

- The legal review is done → add consent and the privacy-policy text, an opt-out in settings, the Roskomnadzor notice; possibly limit what reaches Telegram to a link.
- The volume of sign-ups makes one message per user noisy → a daily digest instead.
