# ADR 0045 — Google Tag Manager in the cabinet, behind consent

- **Status:** accepted by the owner on 2026-10-14 (placement: the cabinet now, the public site when it exists; consent: Consent Mode v2; no cookie banner inside the cabinet — the owner, the same day).
- **Package:** cabinet (`frontend/`, slice `consent`); F4 passes the container id to the production build and opens the Content-Security-Policy for it; `site/` loads the same container when it is built.
- **Context documents:** [ADR 0019](0019-no-session-replay-in-the-cabinet.md); [ARCHITECTURE.md](../design/ARCHITECTURE.md) nfr-4, §14 rule 13, §16.8, §22; [SEO strategy](../seo/STRATEGY.md) 11.3, 18.11.

## Context

- The owner runs marketing and product analytics through a Google Tag Manager container, `GTM-MLQW5VGQ`.
- Google's tags set cookies and send the visitor's identifiers to Google. In the EU that needs consent before any cookie is set (GDPR, ePrivacy); in Russia it is a cross-border transfer of personal data (152-FZ).
- GTM can load any tag its owner adds in its web interface, without a code change: session replay or a heatmap would send what is on the cabinet's screens — meeting titles, notes, Leo's answers — to a third party, which ADR 0019 rules out.
- ADR 0019 keeps one inline script in `index.html`, so the Content-Security-Policy can pin it by hash.

## Decision

1. **Where.** The cabinet loads the container now; the public site loads the same container when it is built. The admin panel loads it too, under the same consent.
2. **Consent first, asked outside the cabinet.** Before GTM loads, the cabinet sets Consent Mode v2 defaults: `ad_storage`, `analytics_storage`, `ad_user_data` and `ad_personalization` denied for everyone. The cabinet shows no cookie banner: the work space stays quiet. The choice — one for analytics and marketing together — lives in the first-party cookie `shosai_consent` for 180 days, shared with the public site on the same domain: the site's banner asks, with accepting and declining equally easy, and the cabinet reads the answer and offers the same switch in Settings → Privacy, where it can be given or withdrawn at any time. Until a person accepts, tags run without cookies.
3. **Loaded from a module, never inline.** The snippet's logic runs from the cabinet's own code after the first render, while the browser is idle; `index.html` keeps its one inline script. The `noscript` iframe is not added: it would reach Google with no consent at all, and the cabinet does not work without JavaScript.
4. **Configured, not coded.** The container id comes from the build variable `VITE_GTM_CONTAINER_ID`; without it neither GTM nor the Privacy switch exists, so development and tests send nothing.
5. **What the container may hold.** Tags that receive page views, funnel events and properties free of user content: GA4, Google Ads and Yandex conversion tags. Not allowed in the container: session replay, heatmaps, form or text capture, or any tag that reads the page's content (ADR 0019). Whoever edits the container keeps to this list; a change to it is a change to this ADR.

## Consequences

- People who decline are counted only by Google's cookieless modelling; people who accept are measured fully.
- The cabinet never interrupts work with a consent question. Until the public site exists, a person's consent comes only from the Privacy setting, so most of the cabinet's traffic is measured cookieless.
- F4's Content-Security-Policy allows `https://www.googletagmanager.com` and the hosts of the allowed tags.
- The legal review of §22 includes the transfer to Google for Russian users.

## Revisit when

- The legal review rules the transfer to Google inadmissible for a group of users.
- A product question needs a tag outside the allowed list.
