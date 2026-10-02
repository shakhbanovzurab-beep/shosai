# ADR 0019 — No session replay in the cabinet

- **Status:** accepted by the owner on 2026-10-02 (F2 planning, decision F2-D5).
- **Package:** F2, frontend foundation (`core/analytics`); S14 owns the product event catalogue.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §14 rule 13, §16.8, nfr-14, §22; [F2 plan](../plan/packages/F2-frontend-foundation.md) §3.10.

## Context

- The draft's cabinet loads Yandex Metrika inline from `index.html` with **webvisor** (session replay) and click maps on, and GA4 for the marketing funnel.
- Session replay records what is on screen and sends it to Yandex: meeting titles, transcripts, notes, Leo answers. That is user content leaving the platform for a third party, without consent, for people of both data homes.
- The Metrika counter, its goals and the GA4 events carry no user content: page views, funnel steps, tariff and language.

## Decision

1. The SPA keeps the Yandex Metrika counter and its goals, and the GA4 funnel events and user properties, as in the draft.
2. Webvisor and click maps are **off** in the SPA.
3. Metrika is loaded from a module, not from an inline snippet; the pre-paint script stays the only inline script in `index.html`.

## Consequences

- The owner has no screen recordings of the cabinet. Funnels, goals and page views stay.
- No user content reaches Yandex through the cabinet; the legal review of §22 has one transfer less to assess.
- F4 can pin the pre-paint script by its hash in the Content-Security-Policy instead of allowing inline scripts.

## Revisit when

- Session replay becomes necessary for a product question; then only with masking of all user content and the user's consent, after the legal review.
