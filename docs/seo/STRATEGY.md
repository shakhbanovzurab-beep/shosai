# Shosai Search Strategy: SEO, GEO and AIO

This document defines how Shosai becomes visible, correctly understood and
cited in search engines and AI answer systems, and how that visibility turns
into activation and revenue. It describes the target state for `shosai`.

- **Audience:** engineers and coding agents who build or change any public
  Shosai page, and whoever plans content.
- **Tooling:** the `claude-seo` skills installed in `.claude/skills/`. Section 17
  maps every part of this strategy to the skill that executes or checks it.
- **Canonical domain:** `shosai.tech`. The production origin
  `https://shosai.tech` is the only indexable host (6.12).
- **Status:** strategy, not implementation. Section 18 lists the decisions that
  must be made before it can be built; section 19 sums up what is covered.

Numbers in brackets such as `[S24]` point to the section of the original
strategy draft that the text comes from. Appendix A lists them all.

---

## 1. Goal and principle

**Goal.** Make Shosai the most visible and most trusted source for its target
search and AI queries: error-free indexing, dominant topical coverage, a strong
entity graph, high citation rates in AI systems, and the highest possible
conversion of organic demand into activation and revenue.

**Principle.** Do not optimize the site for search engines. Optimize the
**Shosai knowledge system** so that a search engine, an AI system and a person
all get the same precise answer to six questions:

1. What is Shosai?
2. What problem does it solve?
3. Who is it for?
4. How does it work?
5. How is it different, and what are its limits?
6. Where is that proven?

Shosai should not try to rank first by gaming an algorithm. It should be so
useful, specific, original, trusted, well structured, well linked, well
understood, well cited and technically accessible that choosing it as the
relevant source is the easiest option for a search engine or an AI system. `[S114]`

---

## 2. The model

### 2.1 Five layers `[S0]`

| Layer | What it is responsible for |
|---|---|
| **SEO** | Pages are discovered and ranked. |
| **GEO** (generative engine optimization) | Shosai's information is likely to appear in generated answers. |
| **AIO** (AI optimization) | Presence in AI-powered search. AIO = SEO + GEO + entity + citation + AI search monitoring. `[S37]` |
| **Entity SEO** | Shosai is one unambiguous entity. |
| **CRO** (conversion rate optimization) | Organic attention becomes installs, activation and money. |

### 2.2 The funnel `[S0, S54, S97]`

```text
Query → SERP or AI answer → Shosai citation or mention
      → landing page, article or documentation → understanding
      → download → install → signup → first useful action
      → subscription → retention
```

Every step is measured. Search work does not end at the click; it ends at
revenue.

---

## 3. Priority system `[S1]`

Every SEO, GEO or AIO item gets one priority.

| Priority | Meaning | Examples |
|---|---|---|
| **P0 — Critical** | Failure loses or corrupts indexing, entity attribution or conversion. | Lost or wrong indexing, duplicates, soft 404, broken hreflang, blocked crawlers, lost canonical signals, wrong entity attribution, critical conversion defects. |
| **P1 — High impact** | Materially moves organic traffic, topical authority, AI citations, branded search, backlinks or conversion. | Crawl-budget efficiency, internal linking, content for priority clusters. |
| **P2 — Growth** | Scales what already works. | Topical authority, programmatic SEO, international SEO, AI visibility, brand and entity graph, long-tail traffic. |
| **P3 — Experimental** | No sufficient evidence of direct effect. | New AI-readable formats, experimental machine-readable endpoints, non-standard GEO techniques. |

**Rule:** an experimental mechanism never replaces P0 or P1 work.

---

## 4. Rollout phases

The strategy is delivered in three phases. A phase starts only when the previous
one meets its exit condition.

| Phase | Scope | Exit condition |
|---|---|---|
| **1. Technical core and entity foundation** | English only (US and global). Server-rendered or statically generated public pages. Open access for search and AI search crawlers (`OAI-SearchBot`, `PerplexityBot` and the others in 6.3). Base entity schema. 5–7 key comparison pages (versus Otter, Granola, Fireflies and others). Documentation. | All P0 gates in section 13 pass on production. |
| **2. Citation moat and community** | First benchmark (latency and accuracy) published as a linkable asset. Participation in Reddit and Hacker News discussions. AI citation monitoring switched on. | Monitoring produces a stable weekly baseline. |
| **3. International and programmatic SEO** | The remaining 15 languages, 2–3 key regions per quarter, each validated for payback before the next. Template scaling. | Per region: payback validated. |

Consequences of phasing:

- Hreflang (6.8) links only locales that are actually published. A locale is
  added to the mesh when its pages ship, never before.
- Programmatic SEO (8.7) does not start before phase 3.

---

## 5. Entity and positioning

### 5.1 One entity `[S18, S104]`

```text
Shosai
  type:   AI Workspace / SoftwareApplication
  domain: shosai.tech
```

One product, one canonical domain, one consistent identity, many corroborating
sources.

Related entities: Leo (the AI agent), AI Workspace, Meeting Assistant,
Transcription, Translation, Knowledge Base, MCP, Founder. `[S18, S74]`

### 5.2 Consistency everywhere `[S19, S75]`

The following must be identical on the website, documentation, GitHub, social
profiles, directories, reviews, articles and press: brand name, official URL,
product category, description, founder, launch information, features, pricing,
screenshots, links to social profiles, GitHub and documentation.

Do not let these read as four different products: "Shosai AI",
"Shosai.one", "Shosai Workspace", "Shosai Meeting Assistant".

If one source says "Shosai is a meeting bot" and another says "Shosai is a
local AI workspace", entity ambiguity grows and AI answers get worse.

**Fact registry (P0).** The facts above live in one versioned registry in the
repository: brand name, official URL, category statement, short and long
description per locale, founder, launch date, platforms, supported languages,
pricing, data residency and the list of official profiles (`sameAs`). Facts in
website copy (prices, the number of languages, platforms) are rendered from it,
not typed into the text. JSON-LD, `llms.txt`, directory listings and the
expected answers of the accuracy audit (9.6) are taken from it. A value in
JSON-LD or `llms.txt` that contradicts the registry fails the build (13.2).
External profiles and listings are compared with it every quarter (14).

### 5.3 The main differentiator: no-bot architecture

AI systems comparing meeting assistants usually sort them into two groups: bots
that join the call, and tools that capture audio locally. Shosai states its
group explicitly in every short definition on the site (the citation units in
9.3), so that it is placed in the privacy-first, bot-free category.

This is a factual claim and follows the evidence rule in 9.2: it is published
only in the form the product actually implements, and it is updated when the
product changes.

### 5.4 Knowledge graph `[S74]`

Build one graph in which Shosai links to: SoftwareApplication, AI Workspace,
Leo, Meeting Assistant, Transcription, Translation, MCP, Founder, GitHub,
Documentation, social profiles and external references. The same entity always
has the same identifier and the same description.

The capabilities in the graph follow the product scope of the target
architecture (§1), not marketing wording:

```text
Organization ── publishes ──▶ Shosai (SoftwareApplication, AI Workspace)
Shosai ── has ──▶ Leo (AI agent)
          ── has ──▶ Meetings (capture, transcription, translation, notes)
          ── has ──▶ Knowledge (knowledge base, search)
          ── has ──▶ Tasks (tracker)
          ── has ──▶ MCP (access for external AI clients)
Founder (Person) ── founder of ──▶ Organization
```

**Identifiers (P0).** Each entity has one `@id` on the production origin, kept
in the fact registry (5.2) and never changed. The Organization, WebSite and
SoftwareApplication are defined on the homepage
(`https://shosai.tech/#organization`, `#website`, `#software`); Leo and each
capability on its own canonical page; the founder on the About page (8.13).
Every other page references these `@id`s and never defines the entity again. The
`@id`s and names are the same in every locale; only descriptions are localized.
Brand and product names (Shosai, Leo) are never translated.

### 5.5 Founder entity `[S84]`

Maintain one consistent public founder profile that connects
Founder → Shosai → GitHub → technical writing → research → interviews. This
strengthens the link between person, product, research and company.

---

## 6. Technical foundation

### 6.1 Checklist `[S2]`

**P0**

- Crawlability, indexability, canonicalization
- Correct HTTP status codes
- Correct sitemap, `robots.txt` and hreflang
- Internal linking, mobile accessibility, HTTPS
- Rendering, Core Web Vitals
- No accidental `noindex`
- No accidental canonical to another language
- No soft 404, redirect chains or redirect loops
- No orphan pages, no broken internal links
- Path URLs for public pages; no fragment (`#`) routing (6.2)
- No challenge, geo block or IP block for allowed crawlers (6.3)
- Production output uses only the production origin in absolute URLs;
  non-production is never indexable; the production inventory is always
  indexable (6.12)

**P1**

- Crawl-budget efficiency and crawl depth
- URL normalization and parameter handling
- Duplicate control
- Pagination architecture, faceted-navigation policy, archive policy
- Content freshness
- Internal PageRank distribution, semantic navigation, breadcrumbs

### 6.2 URL architecture `[S3]`

Every indexable URL has: one canonical URL, one HTTP representation, one
language, one role, a predictable slug and a stable history.

Check: trailing slash, lowercase, URL encoding, query parameters, duplicate
paths, HTTP → HTTPS, `www` versus non-`www`, language prefixes, legacy URLs,
redirects, canonical, sitemap inclusion.

**Forbidden:** creating thousands of URLs that differ only by parameters, word
order, translation without localization, synonym stuffing, template generation
or trivial text changes. Google treats mass creation of low-value pages,
including with AI, as scaled content abuse.

**Path URLs only; no fragment routing.** Every public indexable page has its own
path URL, such as `https://shosai.tech/pricing`. A fragment never identifies a
public page: no `/#/pricing`, no `/#!/pricing` (Google deprecated its `#!`
crawling scheme in 2015). The browser does not send the part after `#` to the
server, so the server cannot return a status, canonical or content for that
page. Search engines treat every fragment of a URL as one page.

- A canonical, an hreflang `href`, a sitemap `<loc>`, `og:url` and a JSON-LD
  `url` never contain `#`.
- A link from one public page to another is an `<a href>` with the path URL.
  `href="#/…"`, `href="#!…"`, `href="#"` with a click handler and
  `href="javascript:…"` are not links for a crawler.
- Allowed: an in-page anchor on a page that already has its own path URL
  (`/docs/install#linux`), and a JSON-LD `@id` such as
  `https://shosai.tech/#organization`, which is an identifier, not a route.
- The rule covers the public URL space. Routes of the signed-in application are
  outside the indexable inventory (6.12).

**Normal form (P1).** Every public URL has one normal form. Every other spelling
answers with one `301` / `308` to it (6.7):

- the path is lowercase, with words separated by hyphens;
- one trailing-slash convention holds for the whole site;
- the locale is a path segment on the one production origin (6.12), never a
  subdomain, a country domain or a query parameter;
- no `index.html`, no `.html` extension, no double slash.

S17 fixes the trailing-slash convention and the locale that has no prefix once,
from the draft's indexed URLs (6.7, legacy URLs), and they never change
afterwards.

**Query parameters (P1).** What an indexable page shows never depends on a query
parameter, except the page number of a paginated list.

- Tracking and unknown parameters (`utm_*`, `gclid`, `fbclid`, `ref` and any
  parameter the page does not use) return `200` with the canonical of the clean
  URL. They never create a new indexable page.
- Internal links, canonical, hreflang, sitemap URLs and `og:url` carry no
  parameters, except the page number of a paginated list.
- Session ids, user ids and application state never appear in a public URL.

**Pagination (P1).** A paginated list (blog, help centre, changelog):

- links each page to the previous and next one with `<a href>`;
- gives every page a self-referencing canonical, never one to page 1;
- has one URL for page 1: a `?page=1` form redirects to it;
- answers `404` for a page number past the last page;
- backs "load more" and infinite scroll with these URLs.

Pages after the first are indexable and in the sitemap; their title and meta
description carry the page number.

### 6.3 Crawlability `[S4]`

Verify access for: Googlebot, Bingbot, OAI-SearchBot, ChatGPT-User, ClaudeBot,
Claude-SearchBot, PerplexityBot, Applebot, Amazonbot, Common Crawl and any other
relevant crawler.

For each crawler record: crawler, URL, timestamp, HTTP status, response time,
robots decision, content type, content length, canonical, indexability.

Look specifically for blocks caused by: WAF, rate limiting, CDN, firewall, bot
protection, accidental `403`, JavaScript challenges, CAPTCHA, geo blocking.

`OAI-SearchBot` is critical: blocking it removes the site from ChatGPT Search
results.

**Rules.** An *allowed crawler* is one that production `robots.txt` (6.4) lets
fetch the URL. These rules hold for public pages and for the search files:
`robots.txt`, sitemaps, the IndexNow key file, `og:image` files and `llms.txt`.

1. **`robots.txt` is the only access policy.** No other layer blocks or slows an
   allowed crawler: not the edge (NGINX today), rate limits, a WAF, a CDN or
   bot-protection service (Cloudflare or any other, if one is added), a firewall
   or the application.
2. **No challenge.** Public pages and search files are never served behind a
   JavaScript challenge, managed challenge, CAPTCHA or interstitial, for anyone,
   in normal operation. Most AI crawlers do not run JavaScript, so a challenge
   blocks them, whatever its status code. Category-wide bot blocking (an "AI
   bots" block, a "bot fight" mode) stays off for these paths. An emergency
   mitigation during an attack exempts verified allowed crawlers.
3. **Verify by origin, never by user agent.** A crawler is verified only by the
   method its operator publishes: reverse DNS with forward confirmation, the
   published IP ranges, or a Web Bot Auth signature. An exemption keyed on a
   user-agent string alone is forbidden, because anyone can send one. A request
   that claims a crawler's user agent and fails verification is ordinary
   traffic: it gets no exemption and no block of its own, so a stale IP list
   cannot lock out the real crawler.
4. **No `403`; overload is `429` or `503`.** An allowed crawler never receives
   `403` on a public URL. Rate limits do not single out crawlers. When load must
   be shed, the answer is `429` or `503` with `Retry-After`, which crawlers
   understand and back off from; never `403`, a challenge or a redirect.
5. **No geo or IP blocking.** No country, region, network (ASN) or data-center
   address rule applies to public pages and search files. Crawlers run in data
   centers, and Googlebot crawls mainly from addresses in the United States.
6. **Same response as a browser.** A URL returns the same status, robots
   directives, canonical and main content to an allowed crawler, to a browser
   and to every country. The locale comes from the URL, never from the
   visitor's IP or `Accept-Language`, so there is no automatic redirect between
   locales (6.2: one HTTP representation). A different response for a crawler
   is cloaking (15.3).

**Check.**

- **Deploy gate (13.2).** For the smoke set (13.3), `robots.txt`, the sitemap
  index and one `og:image`, a request with each allowed crawler's published
  user agent is compared with a browser request. The gate runs from outside the
  plane, including from a United States address. It fails on a different
  status, different robots directives or canonical, any `403`, `429` or `503`,
  or a challenge: a challenge page, or a marker such as Cloudflare's
  `cf-mitigated: challenge` header. Under rule 3 a spoofed user agent is
  ordinary traffic, so the comparison is valid.
- **Production telemetry (12.7).** A test cannot pose as a verified crawler, so
  the real crawlers are watched in the request log. Any `403` or challenge
  served to a verified allowed crawler on a public URL is a "blocked crawler"
  incident (13.5). The crawler dashboard shows `429` and `503` counts per
  crawler.
- **Edge changes (P1).** Edge, WAF and CDN configuration lives in the repository
  and ships through the release, so every change passes the deploy gate. A
  setting that can change outside the repository (a provider's dashboard or
  default) is covered by the daily scheduled run (13.3).

**Crawl traps (P1).** No public URL space grows without bound. Internal site
search results, filter and sort combinations, calendars and any URL built from
free user input are not linked with `<a href>` from public pages, are disallowed
in production `robots.txt` and are never in the sitemap. Internal links are
root-relative or absolute, never document-relative (`../`), so a wrong base
cannot stack path segments.

### 6.4 `robots.txt` and AI crawler policy `[S5, S36]`

Define a separate policy for each of four access types:

| Access type | Example crawler |
|---|---|
| Search | Googlebot, Bingbot, `OAI-SearchBot`, `Claude-SearchBot`, PerplexityBot |
| Training | `GPTBot`, ClaudeBot |
| User-triggered browsing | `ChatGPT-User` |
| Private application and ads validation | decided per case |

`OAI-SearchBot` is not `GPTBot`, and `Claude-SearchBot` is not `ClaudeBot`. The
first of each pair feeds search; the second crawls for model training. Never
block an AI search crawler by accident.

Production `robots.txt`:

- answers `200`: a `5xx` makes compliant crawlers treat the whole site as
  disallowed;
- never disallows a URL of the indexable inventory (6.12) for a crawler with
  search access;
- names the sitemap index in one line,
  `Sitemap: https://shosai.tech/sitemap.xml`.

Non-production `robots.txt` follows 6.12.

### 6.5 XML sitemap `[S6]`

**P0.** A sitemap contains only URLs that are canonical, indexable, return HTTP
200 and are real public pages.

Check: URL count, duplicates, `3xx`, `4xx`, `5xx`, `noindex`, canonical mismatch,
hreflang mismatch, stale `lastmod`.

**Production only.** Only production serves a sitemap (6.12). Every `<loc>` and
every alternate `href` in it starts with `https://shosai.tech/`.

**Complete inventory.** The sitemap is generated from the list of public pages
the site serves. CI compares the two: a public indexable page missing from the
sitemap, or a sitemap URL that is not a public page, fails the build.

Layout for scale:

```text
sitemap.xml
├── sitemap-pages.xml
├── sitemap-blog.xml
├── sitemap-docs.xml
├── sitemap-products.xml
├── sitemap-languages.xml
└── sitemap-images.xml
```

The sitemap is the complete URL inventory. IndexNow is fast change notification.
They solve different problems and both are used.

### 6.6 IndexNow `[S7]`

Create, update and delete each trigger an IndexNow submission, and only after
production deployment.

**P0.** Before submitting, confirm: the URL exists on production, the HTTP status
is correct, the canonical is correct, the content is deployed, the sitemap and
hreflang are updated.

For a deletion: return `404` or `410`, remove the URL from the sitemap, then
submit the URL explicitly.

**Production only** (6.12). The submitter refuses to run unless the configured
origin is `https://shosai.tech`, and refuses any URL on another host. It runs
only after every production gate in 13.2 has passed. A non-production
environment submits nothing, neither production URLs nor its own, and serves no
IndexNow key file.

IndexNow notifies search engines of a change. It does not guarantee indexing.

### 6.7 HTTP status and canonical `[S8, S9]`

| Status | Meaning |
|---|---|
| `200` | Valid page |
| `301` / `308` | Permanent redirect |
| `302` / `307` | Temporary redirect: conversion experiments only (11.5) |
| `404` | Resource does not exist |
| `410` | Resource intentionally removed |
| `403` | Access restricted |
| `429` | Rate limited |
| `500` | Server failure |
| `503` | Temporarily unavailable (maintenance, overload), with `Retry-After` |

**Maintenance (P0).** Planned or unplanned downtime of public pages answers `503`
with `Retry-After`; never `200` with a maintenance page, never `404`.

**Redirects (P0).**

- A permanent move is `301` or `308`. `302` and `307` are for experiments only.
- One hop: every redirect points at the final URL, which answers `200`. No
  chains, no loops.
- The target has the same purpose and the same language as the old URL.
- Internal links and `og:url` point at final URLs, as the canonical, sitemap and
  hreflang already do (6.5, 6.8, this section).
- Redirects are never removed. The redirect map is versioned in the repository
  and only grows. When a target moves again, every redirect to it is updated,
  so each stays one hop.

**Legacy URLs from the draft (P0).** Every public URL of the draft that is
indexed or linked from other sites keeps working when v2 ships: the same path
with the same content, or one permanent redirect to its successor. Before S17
ships, the list is built from the draft's sitemap and from Search Console's
indexed and most-linked pages. CI checks every entry (13.2).

**Soft 404 is forbidden.** The status the server sends is the only "not found"
signal.

- A URL that matches no page returns `404`. A page removed on purpose returns
  `410`, or `301` / `308` to a page with the same purpose.
- Each of these is a soft 404: the application shell or any other page served
  with `200` for an unknown URL; a "not found" screen drawn by JavaScript after
  a `200`; a `noindex` added by JavaScript in place of a status; a redirect of an
  unknown or removed URL to the homepage or to a page with another purpose; a
  `200` for an unknown slug or an unknown locale prefix.
- **Single-page-app fallback.** Serving the application's `index.html` for any
  path (an NGINX `try_files … /index.html`, a history fallback) is not allowed
  in the public URL space. The fallback answers only paths that match a route
  of the signed-in application, which lies outside the indexable inventory
  (6.12). Every other path returns `404`.

Check after each deploy (13.2): random unguessable paths at the root, under
each public section and under each published locale prefix return `404`; every
URL that left the sitemap since the previous release returns `404`, `410`, or
`301` / `308` to a URL in the current sitemap other than the homepage.

Every indexable page has `<link rel="canonical" href="...">`. Check:
self-canonical, language, protocol, trailing slash, no redirect on the canonical
target, target returns `200`, target is indexable.

Independent localized pages never canonicalize to another language (no Russian
page → English canonical, and the reverse).

### 6.8 Hreflang `[S10]`

All localized variants of a page reference each other. Check: reciprocal links,
self-reference, valid locale codes, consistency with canonical, missing
translations, deleted translations, orphan translations, `x-default`.

**Critical rule:** never publish hreflang pointing at a URL that returns `404`.

The platform supports 16 languages. Per section 4, the mesh contains only the
locales already published.

### 6.9 Rendering `[S64]`

Public SEO pages are as independent as possible from client-only single-page-app
rendering. The content must be available to a crawler without executing a
complex client-side flow.

Check each page four ways: `curl`, HTML source, rendered DOM, and the response a
crawler actually receives.

The title, meta description, robots directives, canonical, hreflang, Open Graph
(8.3) and JSON-LD are in the server response. JavaScript does not add, change or
remove them. Google may keep a `noindex` from the raw HTML after a script
removes it, and may pick either canonical when a script changes it; preview
crawlers do not run JavaScript at all.

Phase 1 requires server-side rendering or static generation for public pages.
Public pages are served by the Next.js public site (ADR 0021, 18.1).

### 6.10 Performance `[S63]`

Track: TTFB, LCP, INP, CLS, FCP, server response time, JavaScript execution,
CSS, fonts, images, cache, compression.

Target: a fast server, a small critical payload, a stable layout and minimal
blocking JavaScript.

### 6.11 Security `[S65]`

Security infrastructure must not break crawler access. Check: TLS, certificates,
CSP, WAF, rate limits, bot rules, redirects, security headers. A legitimate
crawler is not a malicious bot and must not be treated as one. The rules and
checks in 6.3 bind every security layer.

### 6.12 Production and non-production environments `[S2, S7]`

**Production** is one origin: `https://shosai.tech` ([ADR 0040](../adr/0040-shosai-tech-is-the-domain.md)). Until production exists, `shosai.tech` runs the test environment and is treated as non-production: `noindex`, out of every sitemap and search property. The `http://` and `www.`
variants, where they answer at all, redirect permanently in one hop to the same
path on it (6.2). Every other host is **non-production**: local development
(`localhost`, loopback and private addresses, container host names), staging
(`shosai.tech` until production, then a subdomain of it) and any preview or
temporary host.

**The origin comes from configuration.** Each environment sets its origin in
configuration, like all configuration in the project. It is never taken from
the request's `Host` or `X-Forwarded-Host` header, from the build machine, or
from a default in code.

**Absolute URLs on production.** Every absolute URL that the site emits about
itself starts with `https://shosai.tech/`:

| Where | Fields |
|---|---|
| HTML `<head>` | canonical, hreflang `href`, `og:url`, `og:image` |
| JSON-LD | `@id`, `url`, `logo`, `image` and every other value that names a Shosai page or file |
| `robots.txt` | `Sitemap:` |
| Sitemaps | `<loc>`, alternate `href`, `image:loc` |
| IndexNow | `keyLocation`, `urlList`; `host` is `shosai.tech` |
| `llms.txt`, `llms-full.txt` | links to Shosai pages |

These fields are absolute, never relative. A production response that has
`localhost`, a loopback or private address, a port, `http://`,
a staging subdomain, `www.shosai.tech` or any other non-production host in
one of them fails the gate (13.2). Links to other sites (`sameAs`, cited
sources) are not affected.

**Non-production is never indexable.** A non-production environment:

1. sends `X-Robots-Tag: noindex, nofollow` on every response: pages, files,
   images and errors;
2. does not disallow its pages in `robots.txt`, because a crawler that may not
   fetch a page never sees its `noindex` and can still index the bare URL from
   an outside link;
3. serves no sitemap: every `/sitemap*.xml` path returns `404`, and
   `robots.txt` has no `Sitemap:` line;
4. serves no IndexNow key file and submits nothing (6.6).

`noindex` is the default. Only the production configuration switches it off; a
missing or unknown environment setting yields `noindex`. If production is
misconfigured this way, the production indexability gate (13.2) catches it.

**Production is always indexable.** The indexable inventory is the set of URLs
in the production sitemap (6.5). Every URL in it:

- returns `200` directly, without a redirect;
- carries no `noindex` or `none`: not in `<meta name="robots">`, not in a
  crawler-specific meta tag (`googlebot`, `bingbot` and others), not in
  `X-Robots-Tag`, including the crawler-specific form
  `X-Robots-Tag: googlebot: noindex`;
- is not disallowed by production `robots.txt` for a crawler with search access
  (6.4);
- has a self-referencing canonical (6.7).

These rules apply to the response that leaves the edge, not only to the HTML the
application produced: a header added by NGINX, a CDN or a WAF counts. `noindex`
on production is allowed only outside the inventory, for example on routes of
the signed-in application. Such a URL is never in the sitemap and never the
target of a canonical, an hreflang link or `og:url`.

---

## 7. International SEO `[S11]`

Translation is not localization. Each language gets its own: keyword research,
search intent, slug, title, meta description, headings, terminology, examples,
FAQ, call to action, pricing, screenshots, competitors, backlinks, directories,
SERP analysis and AI queries.

Each market has its own chain: query → intent → SERP → content → entity → call
to action.

**Language signals agree (P1).** On every page, `<html lang>`, the hreflang
self-reference, the language of the main content and the language of the slug
are the same. A `lang` that differs from the hreflang self-reference fails the
build (13.2).

**No fallback content (P1).** A page exists in a locale only when its main
content exists in that language. A missing translation means the page is not
published in that locale: it is not in the hreflang mesh and its URL returns
`404`. The English text is never served under another locale's URL. The soft
gate "missing translation in a rare locale" (13.2) reports the gap.

**Reviewed translation (P1).** Machine or AI translation is a draft. A locale
page is published only after a fluent reviewer has checked it, recorded per
locale as `reviewed_at` (8.10). Unreviewed machine translation at scale is the
scaled content abuse of 6.2.

**One entity in every language (P0).** Every locale references the same entity
`@id`s and names (5.4); only descriptions are localized.

---

## 8. Content system

### 8.1 Intent first `[S13]`

Do not create a page only because a keyword exists. Work in this order: query →
intent → SERP → existing demand → user problem → best page type.

Intent classes: informational, navigational, commercial investigation,
transactional, problem-aware, solution-aware, product-aware, comparison,
alternative, how-to, definition, local, technical.

### 8.2 SERP analysis and information gain `[S14, S15]`

For each important cluster analyze: top results, content format, intent, title
and H1 patterns, featured snippets, "People also ask", video, images, forums,
Reddit, product results, AI features, local results, freshness, backlinks,
referring domains, topical coverage.

The goal is not to copy the SERP but to find what is missing from it.

Every new page answers: **what does the user get here that the top 10 results do
not give?** Sources of information gain: own data, benchmarks, experiments,
screenshots, latency measurements, transcripts, datasets, interviews, case
studies, technical details, methodology, original research.

### 8.3 Page requirements `[S12, S92]`

Every money page and content page has: primary intent, primary query, secondary
queries, title, meta description, H1, H2/H3 structure, an intro that answers the
query, semantic entities, internal links, external evidence, FAQ where useful,
examples, tables where useful, original information, author, publication date,
updated date and a clear call to action.

Every expert page also shows: credentials where relevant, sources, methodology,
and a contact or organization.

**Open Graph.** Every page of the indexable inventory (6.12) has these
properties in the server response (6.9), each exactly once:

| Property | Rule |
|---|---|
| `og:title` | Not empty, in the page's language, names the same subject as `<title>`. |
| `og:description` | Not empty, in the page's language, agrees with the meta description. |
| `og:url` | Identical to the page's canonical URL. |
| `og:image` | Absolute URL on the production origin (6.12). Answers `200` with `image/png` or `image/jpeg`, the formats every preview client reads. At least 1200 × 630 px at a 1.91:1 ratio, under 5 MB, not disallowed in `robots.txt`. Text in the image is in the page's language. |
| `og:type` | `website`, or `article` for articles. The Open Graph protocol requires it together with `og:title`, `og:image` and `og:url`. |

**X card (P1).** Every inventory page also has
`twitter:card` set to `summary_large_image`. X falls back to Open Graph for the
title, description and image, so `twitter:title`, `twitter:description` and
`twitter:image` are not repeated. `twitter:site` names the official X account
from the fact registry (5.2), if there is one.

Previews of user content opened by a shared or public link follow the link
visibility rules in §7 of the target architecture, not these rules.

### 8.4 Content brief `[S51]`

Each piece starts from a brief: primary query, search intent, audience, funnel
stage, entities, questions, SERP competitors, information gain, sources, internal
links, external sources, call to action, schema, localization requirements, AI
citation opportunities.

### 8.5 Topical clusters `[S16]`

| Cluster | Topics |
|---|---|
| **Meeting AI** | meeting notes, transcription, summary, action items, agenda, protocol, assistant |
| **Interview AI** | interview assistant, transcription, notes, analysis |
| **Translation** | real-time translation, meeting translation, call translation, multilingual meetings |
| **Knowledge** | knowledge base, meeting knowledge, semantic search, organizational memory |
| **AI Workspace** | AI assistant, AI workspace, AI agent, Leo, MCP |
| **Integrations** | Zoom, Google Meet, Microsoft Teams, Telegram, other workflows |

Each cluster is built as: pillar → supporting pages → use cases → how-to →
comparison → FAQ → original research.

### 8.6 Internal linking `[S17]`

Internal links carry authority, context, entity relationships and the user
journey. Every important page has inbound links, contextual outbound links, a
parent, siblings, related content and a call-to-action destination.

**No orphans (P0).** Every page of the indexable inventory (6.12) has at least
one inbound `<a href>` from another inventory page, and a crawl over internal
links from the homepage reaches it (13.2, crawl closure).

Do not use "click here", "read more" or "learn more" where a specific anchor is
possible.

### 8.7 Programmatic SEO `[S44, S45, S46]`

Programmatic pages are allowed only when all five hold: the page exists, it
satisfies a unique intent, it contains unique information, it has useful internal
links, and it has a conversion path. Ten thousand URLs with the same text and a
replaced keyword are forbidden.

Possible dimensions: use case, industry, role, meeting type, language, country,
tool, integration, template, problem, comparison, alternative, workflow.

**Quality gate before publishing.** All of these must be "yes": unique intent,
unique data, unique examples, unique entities, useful internal links, useful call
to action, search demand, no cannibalization, no duplicate content, indexable,
canonical set, hreflang set, schema set. If any is "no", the page is not
published.

### 8.8 Cannibalization `[S47]`

Detect automatically when one query ranks several Shosai URLs. When that
happens, choose one of: merge, redirect, canonicalize, differentiate the intent,
or change the internal link architecture.

**Consolidation (P1).** A merge follows one procedure, in one release: the
strongest page stays; the useful content of the others moves into it; each
merged URL redirects to it in one hop (6.7) in every published locale; internal
links, hreflang and sitemaps are updated; IndexNow is sent for the merged URLs
and the target.

### 8.9 Lifecycle, decay and refresh `[S48, S49, S50]`

Lifecycle: research → brief → production → technical validation → publish →
IndexNow → index monitoring → ranking monitoring → conversion monitoring →
refresh → consolidate or delete.

Each page tracks: `last_updated`, traffic over 30 and 90 days, impressions, CTR,
ranking, backlinks, AI citations, conversion.

Decay signals: traffic, rank, CTR or AI citations fall; competitor coverage
grows; the SERP changes; facts go out of date.

**Decay thresholds (P2).** A page enters the refresh queue when, over 90 days
against the previous 90, its clicks or its AI citations fall by 30% or more, for
pages with at least 100 clicks or 10 citations in the earlier period. These are
initial values, revised once the phase 2 baseline is stable.

Never update a page only to change its date. A refresh means new data, examples,
screenshots, sources, benchmarks or sections, corrected facts, or changed product
capabilities.

### 8.10 Freshness and dates `[S93, S94, S95]`

Detect automatically the pages affected when any of these change: pricing,
features, integrations, product behavior, supported languages, benchmarks,
screenshots. A page must never mix pricing from one year with the product of
another.

Store on every page: `published_at`, `updated_at`, `reviewed_at`,
`product_version`, `owner`. For research also: `dataset_version`,
`model_version`, `test_date`, `environment`. The owner is the person who reviews
the page and answers for its facts.

**One date, three places (P1).** The visible dates, JSON-LD `datePublished` and
`dateModified`, and the sitemap `<lastmod>` all come from `published_at` and
`updated_at`. `updated_at` changes only with a significant change (8.9), never
with a template, footer or rebuild. A JSON-LD `dateModified` that differs from
the sitemap `<lastmod>` fails the build (13.2).

**Review age (P1).** A page that states prices, features, platforms, languages
or competitor facts is reviewed at least every 90 days. An older `reviewed_at`
is a soft gate warning (13.2).

When the product changes: update documentation → landing pages → structured data
→ the `llms.txt` layer → sitemap → IndexNow → then monitor AI answers.

### 8.11 Content types `[S52]`

Landing pages, product pages, use-case pages, comparison pages, alternative
pages, documentation, help center, templates, glossary, research, benchmarks,
case studies, engineering articles, changelog, security, pricing, integration
pages.

| Type | Requirements |
|---|---|
| **Documentation** `[S85]` | Indexable where appropriate, canonical, hreflang, searchable, internally linked, versioned, dated, technically accurate. Documentation is especially valuable for AI systems because it contains concrete facts rather than marketing claims. |
| **Help center** `[S86]` | Each article: problem, answer, steps, examples, limitations, related articles. No thin FAQ pages. |
| **Glossary** `[S87]` | Authoritative definitions of terms such as AI meeting assistant, meeting transcription, speaker diarization, real-time translation, AI workspace, MCP, AI agent, meeting protocol, action item. Each entry: definition, examples, related concepts, and how Shosai implements it where relevant. |
| **Comparison** `[S88]` | Shosai versus Granola, Otter, Fireflies, Fathom. Factual, current, sourced, date-stamped, feature by feature. Never a page whose only purpose is to say Shosai is better. |
| **Alternatives** `[S89]` | "Granola alternatives" and similar. Each page explains who needs an alternative, which dimensions matter, how the products differ and which workflow fits each product. |
| **Templates** `[S53]` | Indexable templates: meeting agenda, notes, protocol, interview notes, action items, one-on-one, retrospective, product meeting, sales meeting. Each one really works and has a downloadable version, an example, an explanation, FAQ, a call to action and internal links. |
| **Images** `[S61]` | Descriptive filenames, alt text, dimensions, compression, WebP and AVIF, responsive images, lazy loading, image sitemap where useful, captions, surrounding context. Create original screenshots, product UI, diagrams, architecture and benchmark charts. |
| **Video** `[S62]` | Title, description, transcript, chapters, thumbnail, structured data, page embedding, relevant surrounding text. A video is a standalone content asset. |

### 8.12 Structured data `[S20, S21]`

Use only schema types that match the actual content. Candidates: Organization,
SoftwareApplication, WebSite, WebPage, Article, BlogPosting, Person, Product,
BreadcrumbList, FAQPage, HowTo.

Link entities through `@id`: Organization → SoftwareApplication → WebSite →
WebPage → Article.

Structured data helps search engines understand a page. It does not guarantee a
rich result or a higher position. FAQPage and HowTo no longer produce Google rich
results (HowTo since 2023, FAQ since May 2026); use them only where they describe
the content, never for a search feature.

CI validates: valid JSON, schema validity, required properties, URL validity
(absolute, on the production origin per 6.12), `@id`, consistency with
canonical, entity references, duplicate entities, stale data. Pipeline:
generate → validate → build → deploy → crawl smoke test.

**Site name (P1).** The homepage defines the `WebSite` entity with `name`
"Shosai" and `url` `https://shosai.tech/`, from the fact registry (5.2).
Every page has `og:site_name` with the same name, and title suffixes use it too.
`alternateName` is set only if the registry defines one. Google chooses the site
name shown in results from these signals.

**Breadcrumbs (P2).** `BreadcrumbList` appears only on a page that shows a
breadcrumb trail, and lists the same items with the same URLs. The trail follows
the URL hierarchy.

### 8.13 Trust pages and authorship `[S92]`

**Trust pages (P1).** The site has an About page (what Shosai is, the company,
the founder), Contact (working channels that get answers), Pricing, Privacy
policy, Terms, Security and data residency, and a Changelog. Each is indexable,
in the sitemap and linked from the footer of every public page. Their facts come
from the fact registry (5.2), and the Organization JSON-LD references them. The
company's legal name and registration details appear as the law of each market
requires (18.11).

**Claims match the system (P0).** What the Security, Privacy and residency pages,
or any other copy, say about where data lives, who processes it and how it is
protected matches the target architecture, including its accepted exceptions.
For example, the files of the EU home stay in Russia until its bucket moves to
the EU ([ADR 0044](../adr/0044-a-bucket-per-data-home.md)), and a claim that depends
on the legal review in §22 of the target architecture waits for its result. A
claim the architecture does not support is not published. A change of residency
or of a provider updates these pages in the same release.

**Authors (P1).** Every article, research report and benchmark names an
accountable person; documentation names an accountable person or team. Each
author has a profile page (`Person` with `@id`, role, relevant experience and
`sameAs`), and the byline links to it. Article JSON-LD references the author's
`@id`. No anonymous bylines such as "Admin" or "Editorial" on articles and
research.

### 8.14 Images and visual search `[S61]`

These rules add to the image requirements in 8.11.

**Crawlable images (P1).** A content image is an `<img>` (or `<picture>`) with
`src`, never a CSS background, which search engines do not index. It has `alt`
in the page's language that says what the image shows. A decorative image has
`alt=""`. A content `<img>` without an `alt` attribute fails the build (13.2).

**Charts and diagrams (P1).** The data or the statement a chart or diagram shows
is also in the HTML, as text or a table next to it, inside a `<figure>` with a
`<figcaption>`. Crawlers and AI systems read the text, not the pixels.

**Large previews (P1).** Inventory pages send the robots directive
`max-image-preview:large`, and an article's lead image is at least 1200 px wide.
Google Discover and large image previews in results need both.

**Attribution (P2).** Original screenshots, diagrams and benchmark charts carry
IPTC or XMP creator, credit and copyright. Images meant for reuse (benchmark
charts) also carry `ImageObject` `creator`, `copyrightNotice` and `license`, so
reuse credits Shosai.

Visual search (Lens, Circle to Search, AI Mode) uses the same signals: original
images, descriptive context and alt text. No separate lever is assumed.

---

## 9. GEO: being cited by AI systems

GEO is not "writing text for ChatGPT". The task is to make Shosai's
information understandable, verifiable, citable and unambiguously tied to the
Shosai entity. `[S22]`

### 9.1 Direct answers `[S23]`

The first screen of every key page quickly answers: what is Shosai, who is it
for, what does it do, how does it work, what makes it different.

Use concise definitions, factual claims, structured lists, tables, dates,
numbers, explicit entities and explicit relationships.

### 9.2 Citation engineering `[S24, S26]`

Write claims as: claim + entity + specific fact + context + date + evidence.

- **Weak:** "Shosai makes meetings smarter."
- **Strong:** "Shosai records the microphone and system audio on the user's
  device without a meeting bot. After the meeting, Leo can extract decisions,
  commitments, risks and open questions."

Every important claim is specific, verifiable, attributable, current and
self-contained.

Strong claims carry a full chain: claim → evidence → source → methodology →
date. This applies especially to benchmarks, latency, accuracy, pricing, market
statistics, feature comparisons, performance, security and infrastructure.

**Canonical source per fact (P1).** Each fact in the registry (5.2) names one
canonical page: prices on the pricing page, residency on the security page,
versions on the changelog, platforms and languages on the product page. Another
page that states the fact repeats the registry value and links to that page, so
people and AI systems find one authoritative source.

### 9.3 Citation units `[S25]`

Create blocks that can be quoted on their own: definition, fact, statistic,
methodology, result, comparison, limitation, example. Do not bury an important
fact inside five paragraphs of marketing copy.

### 9.4 Original research and benchmarks `[S27, S28]`

Shosai becomes a source of data, not only a product. Publish: transcription
benchmarks, translation latency tests, meeting-AI benchmarks, model evaluations,
multilingual evaluations, meeting workflow experiments, AI assistant benchmarks,
productivity experiments, cost comparisons.

Each study states: question, methodology, dataset, environment, variables,
results, limitations, raw data, conclusion, date.

Example: "AI Meeting Assistant Benchmark 2026", comparing latency, transcription
accuracy, speaker diarization, translation latency, language coverage,
hallucination rate, action-item extraction, summary quality, cost and privacy
model. **The methodology is public.**

**Corrections (P1).** Results are versioned. A published result is never
changed silently: a correction is dated and described on the study page, and the
previous version stays available.

### 9.5 Machine-readable layer `[S35]`

Shosai may serve `/llms.txt` and `/llms-full.txt`. Treat them as an
additional machine-readable interface, not as a proven ranking factor (P3).

The layer covers product, features, pricing, documentation, security,
limitations, FAQ, API, MCP and changelog, and must never contradict the website,
documentation, social profiles or directories.

### 9.6 Answer accuracy and hallucination defense `[S33, S34]`

Run an automated audit: expected fact → AI answer → diff → correct, missing or
incorrect. Check: name, category, features, pricing, languages, platforms,
privacy, bot or no bot, Leo, MCP, limitations.

When an AI system describes Shosai wrongly:

1. Identify the wrong claim.
2. Find the authoritative source.
3. Create a canonical factual page.
4. Add structured data.
5. Add external corroboration.
6. Strengthen entity consistency.
7. Monitor again.

Never try to correct hallucinations with SEO spam.

---

## 10. Authority

### 10.1 Brand search `[S38, S39]`

Brand query set: `shosai`, `shosai ai`, `shosai.tech`, `whisperer.one`,
`shosai workspace`, `shosai meetings`, `shosai leo`,
`shosai transcription`, `shosai translation`, `shosai mcp`.

Monitor: SERP, sitelinks, knowledge and entity signals, branded snippets, AI
mentions, incorrect descriptions, competitors intercepting brand queries.

Aim to control the first page for branded queries through: the official website,
documentation, GitHub, social profiles, product directories, reviews, articles,
interviews, Product Hunt, G2, AlternativeTo, StackShare and relevant communities.

### 10.2 Links `[S40, S41, S42, S43]`

Principle: do not buy many links. Build a network of independent confirmations
that Shosai exists and is authoritative.

Priority order for a link: topical relevance, editorial placement, trust,
traffic, uniqueness, authority.

Sources: technical publications, SaaS and AI directories, startup databases,
GitHub, Product Hunt, G2, AlternativeTo, StackShare, founder interviews,
podcasts, YouTube, research publications, benchmark references, guest articles,
digital PR, citations of original research.

Linkable assets to create: benchmarks, datasets, calculators, templates,
reports, original research, statistics, engineering articles, open-source tools,
documentation, glossaries, comparison databases.

Unlinked mentions: search regularly for "Shosai", "shosai.tech", "whisperer.one" and
"Shosai AI"; for each mention check context, authority and whether a link
exists. A mention without a link is an outreach candidate.

### 10.3 Digital PR and community `[S82, S83]`

PR occasions: benchmark release, research, product launch, major feature,
open-source release, engineering achievement, multilingual or translation
benchmark, AI workspace research. No mass link buying.

Work where potential users actually are: GitHub, Reddit, Hacker News, Product
Hunt, Indie Hackers, relevant forums, developer and AI communities.

Rule: usefulness first, the link second.

### 10.4 Reviews and reputation `[S90, S91]`

Collect authentic reviews and record source, date, product version, user context
and verified status where applicable. Never generate fake reviews.

Monitor "Shosai", "Shosai AI", "shosai.tech", "whisperer.one" and "Leo" across search, AI
systems, Reddit, GitHub, directories and review platforms. Correct errors through
authoritative sources.

---

## 11. Product-led search and conversion

### 11.1 Bridge from search to product `[S76, S79]`

Every SEO asset has a logical bridge: search problem → useful solution →
Shosai → download → activation. An article that ends at a generic homepage is
not acceptable.

Examples: meeting protocol template → download → Shosai; meeting
transcription → product explanation → install; AI meeting assistant → product →
client download.

### 11.2 Free tools and assets `[S77, S78]`

Useful free tools: meeting agenda generator, meeting notes generator, meeting
protocol generator, interview questions generator, action items generator,
transcription formatter, meeting duration calculator, meeting cost calculator,
AI meeting ROI calculator.

A tool must really work. No fake generators built only for SEO; deceptive fake
functionality is a pattern Google calls out as a problem.

Free assets: DOCX, PDF, Markdown, Notion and Google Docs templates, checklists,
meeting frameworks, interview frameworks. Where possible: no signup → immediate
value → optional Shosai call to action.

### 11.3 Revenue attribution `[S55, S97]`

Minimum dimensions: query, landing page, cluster, country, language, device,
source, medium, campaign, signup, activation, subscription, revenue.

Report revenue per organic landing page, per cluster, per country and per
language. The goal is not maximum traffic but high-intent organic revenue.

**Funnel events (P1).** Each step of the funnel in 2.2 is one named event with the
same definition in search reports and product analytics: landing view,
call-to-action click, download start, first launch of the client, signup, first
useful action (18.13), subscription, renewal. Signup, first useful action and
subscription are recorded on the server, not only in the browser.

**From the web to the client (P1).** The first touch (landing URL, channel,
query when known, locale) survives the move from the website to a native client
and is joined to the account at signup. Revenue per landing page then includes
people who sign up in a client. The mechanism goes through the privacy review
(18.11).

**AI channel (P1).** Visits from AI assistants are their own channel, separate
from organic search and referral. They are recognized by referrer domain from a
maintained list (`chatgpt.com`, `perplexity.ai`, `gemini.google.com`,
`copilot.microsoft.com`, `claude.ai` and others) and by the `utm_source` values
assistants add, such as `utm_source=chatgpt.com`. Many AI visits arrive without
a referrer, so this channel is a lower bound.

### 11.4 First-party data flywheel `[S80, S81, S111, S112]`

The strategy generates its own data: search queries, content performance,
template and tool usage, activation, conversion, AI visibility. This moves the
work from keyword-driven SEO to a product- and data-driven search strategy.

```text
good product → real user data → original research → unique content
→ search visibility → AI citations → backlinks → entity authority
→ brand search → organic users → revenue → more research
```

Insights from product usage are used only anonymized and aggregated, and only
within privacy and legal requirements.

This loop is the moat. It is far stronger than ten thousand SEO pages.

### 11.5 Conversion experiments

**Experiments do not change what search sees (P1).** A test on a public page:

- shows crawlers the same variants as users; anything else is cloaking (15.3);
- reaches a variant on a separate URL by `302`, never `301`, and the variant
  carries a canonical to the original;
- does not change the original's canonical, robots directives, structured data
  or hreflang;
- ends when it has a result; the winner then replaces the original.

---

## 12. Measurement

### 12.1 Search surfaces `[S29, S107]`

Track presence on: Google Search, Google AI Overviews, Google AI Mode, Google
Discover, Bing, Copilot, ChatGPT Search, Perplexity, Gemini, YouTube, Reddit,
GitHub and product directories. Shosai should be present wherever discovery
actually happens.

For each AI platform keep a record of: surface, crawler, index source, citation
behavior, visibility and monitoring method. `[S37]`

Watch for new platform mechanisms such as Google's preferred sources: AI
visibility depends on the publisher, entity and source relationship, not only on
SEO. `[S106]`

### 12.2 Search engine analytics `[S56, S71]`

| Source | Metrics |
|---|---|
| **Google** | impressions, clicks, CTR, position, indexed pages, queries, countries, devices |
| **Bing** | clicks, impressions, rankings, crawl, AI Performance report, cited pages |
| **Yandex** | impressions, clicks, CTR, positions, indexing, crawl |

Monitor Search Console automatically for: coverage changes, indexing errors,
manual actions, security issues, crawl anomalies, performance drops, query
shifts.

**Properties (P0).** Search Console holds a Domain property for `shosai.tech`,
verified through DNS. It also covers its subdomains, so an indexed staging
URL shows up there. Bing Webmaster Tools verifies the same domain (P0), and so
does Yandex Webmaster for the Russian market (P1). Every property has at least
two owners from the company, never one person's account alone. The production
sitemap index is submitted in each.

**AI surfaces (P1).** The AI metrics in 12.4 also read Search Console's
generative AI performance report (AI Overviews and AI Mode impressions) and
Bing's AI Performance report. AI Mode clicks are counted in the ordinary web
totals and cannot be split out.

### 12.3 AI visibility dataset `[S30, S31, S72]`

Each day or week: run the priority queries against the AI engines, capture the
answer, extract mentions and citations, compare with the previous run, and store
the result with history.

Record per observation: query, country, language, date, engine, model or
surface, whether Shosai was mentioned, whether it was cited, citation URL,
citation position, whether it was recommended (offered as a choice for the
user's need) and at what rank, competitors, features attributed, errors,
sentiment and context.

**Query tags (P1).** Each query carries its cluster (8.5), intent class (8.1),
funnel stage and language, so every metric in 12.4 can be reported per topic and
intent. The query matrix is versioned. A change to it starts a new baseline, so
trends compare like with like.

**Sampling (P1).** AI answers vary between runs. Each query runs a fixed number
of times per engine and run (at least three), in a clean session without
personalization, with a fixed country and language. Results are rates with their
sample size. Raw answers are stored.

Minimum query matrix:

| Category | Example queries |
|---|---|
| Generic | best AI meeting assistant, AI meeting assistant, meeting transcription software, AI meeting notes, AI meeting summary |
| Differentiation | AI meeting assistant without bot, meeting assistant without Zoom bot, local meeting transcription, privacy-focused meeting assistant |
| Product | Shosai AI, Shosai AI Workspace, Shosai Leo, Shosai meeting assistant |
| Comparison | Granola alternatives, Otter alternatives, AI meeting assistant alternatives |
| Use case | AI for interviews, for meetings, for sales meetings, for product meetings, for developers |
| Translation | real-time meeting translation, AI call translation, meeting translator, live speech translation |

### 12.4 AI metrics `[S32, S57, S105]`

Mention rate, citation rate, citation share, unique cited URLs, query coverage,
entity accuracy, feature accuracy, competitor share of voice, AI traffic,
AI-assisted conversion.

An AI citation is a visibility signal. It is not a click and not a conversion.

"ChatGPT mentioned Shosai" is not a measurement. A measurement combines
mention, citation, correctness, query relevance, competitor context and
conversion.

**Definitions (P1).** Over the answers of one run (12.3):

| Metric | Definition |
|---|---|
| Mention rate | answers that name Shosai ÷ answers |
| Citation rate | answers that link a `shosai.tech` URL ÷ answers |
| Recommendation rate | answers that recommend Shosai for the asked need ÷ answers |
| Citation share | links to `shosai.tech` ÷ all links in the answers |
| Query coverage | queries with at least one mention ÷ queries |
| Entity accuracy | facts stated correctly ÷ facts stated, checked against the fact registry (5.2) |

Each metric is reported per engine, cluster, intent, language and country, with
the sample size.

### 12.5 AI visibility regression `[S73]`

When the citation rate falls, check: content freshness, entity consistency,
crawlability, competitors being cited instead, SERP changes, source quality,
query demand, AI model changes. A fall in citation rate is not automatically an
SEO penalty.

### 12.6 Share of voice and competitors `[S58, S59, S60]`

For each priority cluster: Shosai visibility divided by total relevant
visibility, counted separately for Google, Bing, AI search, branded and
non-branded queries.

Competitors to track: Granola, Otter, Fireflies, Fathom, Notta, Wispr, Parakeet
and any other real SERP competitor. Compare not only domains but queries, pages,
entities, backlinks, topics, features, citations, AI mentions and content gaps.

Competitor share in AI answers uses the same answers and definitions (12.3,
12.4): each competitor's mention, citation and recommendation rates.

For each priority query compare Shosai with the top 10 on: content depth,
unique information, backlinks, domain authority, entities, freshness, UX, intent
satisfaction, structured data, internal links and AI citations.

### 12.7 Crawler telemetry `[S66]`

Log per request: crawler, verification result (6.3), URL, status, latency,
bytes, cache, robots decision, canonical, indexability, and whether a challenge
was served. Dashboard by crawler: Googlebot, Bingbot, OAI-SearchBot, ClaudeBot,
Claude-SearchBot, PerplexityBot.

**Retention (P2).** Daily aggregates per crawler, URL and status go to the search
data store (12.8) and are kept for at least 13 months, for comparison with the
same month a year earlier. Raw logs follow the shorter retention of the target
architecture (§16).

### 12.8 Data storage `[S96]`

Keep search data logically separate from product data: queries, pages, rankings,
clicks, impressions, crawls, indexing, citations, mentions, competitors,
conversions, revenue.

### 12.9 Scorecard `[S98, S99]`

There is no single SEO score. Eight dimensions are measured, each with its own
metrics: technical health, content quality, topical authority, entity strength,
AI visibility, link authority, conversion, revenue.

| Group | North-star metrics |
|---|---|
| **Visibility** | non-brand impressions, top-3 keywords, top-10 keywords, share of search |
| **Authority** | referring domains, topical authority, brand mentions |
| **AI** | mention rate, citation rate, citation share, entity accuracy |
| **Business** | organic signups, activation, subscriptions, revenue, revenue per landing page |

---

## 13. Quality gates and deployment

### 13.1 Governance for a new public page `[S100]`

Intent → keyword → entity → content → internal links → metadata → schema →
canonical → hreflang → sitemap → QA → deploy → IndexNow → monitoring.

### 13.2 CI gates `[S67]`

CI validation is split into hard and soft gates.

**Hard gates — the pipeline stops.** These are deterministic correctness errors.
Each gate runs at the earliest stage that can see the error:

| Stage | Checks | On failure |
|---|---|---|
| **Build** | Public pages rendered with the production configuration, sitemaps, `robots.txt`, JSON-LD, tests of the IndexNow submitter | The build fails; nothing is deployed. |
| **Staging** | The deployed staging host (6.12) | The release does not reach production. |
| **Production** | The production host right after deploy, before IndexNow | IndexNow is not sent; the release is rolled back to the previous image, which the release keeps for that purpose (target architecture §14, rule 11). |

| Gate | Fails when | Stage |
|---|---|---|
| Canonical | missing, more than one, relative, not self-referencing on an inventory page, or its target redirects, is not `200` or is not indexable (6.7) | build, production |
| Sitemap and hreflang | a `404` URL in the sitemap or hreflang; invalid hreflang; broken sitemap; a public indexable page missing from the sitemap, or a sitemap URL that is not a public page (6.5) | build, production |
| Structured data | JSON-LD syntax or schema error | build |
| Status and soft 404 | a wrong HTTP status; a soft 404 as 6.7 defines it; an unknown-path probe or a page number past the last page (6.2) that does not return `404`; a URL removed from the sitemap that does not return `404`, `410`, or `301` / `308` to a current sitemap URL other than the homepage | staging, production |
| Redirects | a chain longer than one hop; a loop; a `302` / `307` outside an experiment; a redirect to another language; an internal link or `og:url` that redirects (6.7) | build, production |
| Legacy URLs | an entry of the draft's legacy URL list that does not return `200` or one permanent redirect to a `200` URL (6.7) | staging, production |
| Crawl closure | a crawl over `<a href>` links from the homepage misses an inventory URL (an orphan, 8.6), or reaches a URL that is not an inventory page, a redirect, a path disallowed in `robots.txt`, a route of the signed-in application or a file download (a crawl trap, 6.3) | build |
| Internal links | a broken internal link | build |
| Page basics | missing or duplicate title, missing H1, missing `lang` | build |
| `robots.txt` | invalid; not `200`; disallows an inventory URL for a crawler with search access; a missing or wrong `Sitemap:` line (6.4) | build, production |
| Production indexability | an inventory URL that does not return `200` directly, or has `noindex` or `none` in a meta tag or in `X-Robots-Tag`, including the crawler-specific forms (6.12) | build, production |
| Head drift | the title, robots directives, canonical, hreflang, Open Graph or JSON-LD differ between the server response and the rendered DOM (6.9) | build |
| Open Graph | `og:title`, `og:description`, `og:url`, `og:image`, `og:type` or `twitter:card` missing, empty or repeated; `og:url` differs from the canonical; `og:image` breaks a rule of 8.3 | build (tags, image file), production (image fetch) |
| Language signals | `<html lang>` differs from the hreflang self-reference (7) | build |
| Entity facts | a JSON-LD or `llms.txt` value contradicts the fact registry (5.2); an entity is defined under another `@id` (5.4) | build |
| Dates | JSON-LD `dateModified` differs from the sitemap `<lastmod>` (8.10) | build |
| Images | a content `<img>` without an `alt` attribute (8.14) | build |
| Fragment routing | a canonical, hreflang `href`, sitemap `<loc>`, `og:url` or JSON-LD `url` contains `#`; a link between public pages has an `href` starting with `#/`, `#!` or `javascript:` (6.2) | build |
| Production origin | a field listed in 6.12 is relative or does not start with `https://shosai.tech/`; the IndexNow `host` is not `shosai.tech` | build, production |
| Non-production exposure | a staging response without `X-Robots-Tag: noindex`; a `/sitemap*.xml` path that does not return `404`; a `Sitemap:` line or a `Disallow` of pages in `robots.txt`; a served IndexNow key file; an IndexNow submitter that does not refuse a non-production origin or a URL on another host (6.6, 6.12) | build (submitter), staging |
| Crawler access | for the smoke set, `robots.txt`, the sitemap index and one `og:image`, a request with an allowed crawler's user agent, sent from outside the plane and from a United States address, gets a different status, robots directives or canonical than a browser request, a `403`, `429` or `503`, or a challenge (6.3) | staging, production |

**Soft gates — a warning, the build passes:**

- missing external citations
- delayed metric updates
- missing translation in a rare locale
- `reviewed_at` older than 90 days on a page with facts that change (8.10)

### 13.3 Regression tests on every deploy `[S68]`

Check on critical URLs: canonical, robots, sitemap, hreflang, schema, status,
redirects, metadata, Open Graph, the origin of absolute URLs, crawler access and
the `404` for unknown URLs. These are the staging and production gates of 13.2;
on staging the same run also checks the non-production rules of 6.12.

Minimum smoke set: homepage, pricing, product, documentation, blog, each
published language, each important cluster.

**Scheduled run (P1).** The production checks for `robots.txt`, indexability,
crawler access and the smoke set also run daily from outside the plane, with the
external probes of the target architecture (§16), not only on deploy. A
certificate, DNS record, provider default or edge setting can change without a
release. A failure is an incident (13.5).

### 13.4 Deployment pipeline `[S69]`

```text
code → SEO validation → content validation → schema validation
→ sitemap generation → hreflang validation → build
→ deploy to staging → staging gates → deploy to production
→ production smoke test → HTTP verification → IndexNow → monitoring
```

Staging comes before production, as in the release of the target architecture
(§17). IndexNow is always the last step: after production deployment, and only
when every production gate has passed.

### 13.5 Incident runbooks `[S70]`

A runbook exists for each of: traffic drop, index drop, deindexation, canonical
corruption, hreflang corruption, sitemap corruption, robots corruption, `5xx`
spike, blocked crawler, AI visibility drop, soft-404 outbreak.

### 13.6 Definition of done `[S115]`

An SEO, GEO or AIO task is complete only when every item holds:

- [ ] Search intent, target query and page type defined
- [ ] Entity defined
- [ ] Information gain identified
- [ ] Content created, with original value added
- [ ] Internal links added
- [ ] External sources verified
- [ ] Title, meta description, H1 and Open Graph validated
- [ ] Canonical, hreflang and schema validated
- [ ] HTTP status and robots validated
- [ ] Sitemap updated
- [ ] Production deployment complete and production URL verified
- [ ] IndexNow submitted where applicable
- [ ] Search Console and Bing monitored
- [ ] AI visibility monitored
- [ ] Conversion tracked and revenue attributable

---

## 14. Operating cadence

| Cadence | What happens |
|---|---|
| **Weekly** `[S108]` | Collect → analyze → identify the gap → build → publish → index → measure → refresh. |
| **Monthly** `[S109]` | Review top winning and losing queries, new queries, new competitors, content gaps, and changes in AI citations, backlinks, entities, conversion and revenue. |
| **Quarterly** `[S110]` | Review topical coverage, backlinks, brand mentions, entity consistency, AI visibility, competitor movement, international performance, programmatic-page quality, content decay and technical debt. |

---

## 15. Rules

### 15.1 Four questions for any hypothesis `[S102]`

1. Does it help the user?
2. Does it make the page more understandable?
3. Does it create unique value?
4. Can the business effect be measured?

If the answers are no, the hypothesis is rejected.

### 15.2 Six questions for any GEO material `[S103]`

Can an AI system identify the entity, the claim, the evidence and the date? Can
it quote the relevant section? Can it link to the canonical source?

### 15.3 Never do `[S101]`

Keyword stuffing, hidden text, cloaking, doorway pages, fake generators, mass
low-value AI pages, spun content, duplicate translations, fake reviews,
automated spam comments, private blog networks, irrelevant link farms, purchased
toxic links, misleading structured data, fake statistics, fabricated citations.

### 15.4 The twenty rules `[S116]`

1. No page without search intent.
2. No page without unique value.
3. Do not scale thin content.
4. IndexNow is not a guarantee of indexing.
5. Structured data is not a guarantee of ranking.
6. An AI citation is not traffic.
7. Traffic is not revenue.
8. Translation is not localization.
9. A mention is not authority.
10. A backlink is not topical authority.
11. Do not block legitimate search and AI crawlers.
12. No soft 404.
13. No contradictions between canonical and hreflang.
14. Programmatic SEO must not produce SEO junk.
15. Do not publish unconfirmed claims.
16. No fake reviews and no fake data.
17. Every important claim has evidence.
18. Every important entity is unambiguous.
19. Every SEO page has a measurable business purpose.
20. SEO ends at revenue, not at the click.

---

## 16. The measure of success

The main indicator is not traffic, the number of indexed pages, the number of
keywords or the number of AI mentions. It is **organic and AI search revenue**,
decomposed as: `[S117]`

```text
search demand × visibility × CTR × activation × conversion × ARPU
```

The work must raise visibility, authority, AI citation, brand search, conversion
and revenue together.

**Strategic objective.** `[S118]`

| When someone… | Shosai… |
|---|---|
| searches | appears |
| asks an AI system | is considered |
| needs a source, as an AI system | can be cited |
| compares products | is in the consideration set |
| searches the brand | owns the entity |
| needs the product | is the destination |
| visits | converts |
| converts | generates revenue |

This system as a whole, not a collection of SEO tricks, is the target search
architecture for Shosai.

---

## 17. Executing the strategy with `claude-seo`

The `claude-seo` skills in `.claude/skills/` are the working tools for this
strategy. Use the skill named here rather than improvising the analysis.

### 17.1 Strategy area → skill

| Strategy area | Sections | Skill |
|---|---|---|
| Full-site audit, scored and prioritized | 6, 13 | `seo-audit` |
| One URL, all aspects | 8.3 | `seo-page` |
| Crawlability, indexability, status codes, canonical, redirects, rendering, Core Web Vitals, IndexNow, security headers, environments | 6.1–6.3, 6.6, 6.7, 6.9–6.12 | `seo-technical` |
| Sitemap validation and generation | 6.5 | `seo-sitemap` |
| Hreflang and international setup | 6.8, 7 | `seo-hreflang` |
| JSON-LD detection, validation, generation | 8.12 | `seo-schema` |
| Content quality, E-E-A-T, citation readiness, trust pages, authors | 8.3, 8.13, 9.1–9.3 | `seo-content` |
| Content briefs | 8.4 | `seo-content-brief` |
| Topical clusters and internal link architecture | 8.5, 8.6 | `seo-cluster` |
| Intent and page-type mismatch against the SERP | 8.1, 8.2 | `seo-sxo` |
| Programmatic SEO planning and thin-content safeguards | 8.7, 8.8 | `seo-programmatic` |
| Comparison and alternatives pages | 8.11 | `seo-competitor-pages` |
| Image optimization and visual search | 8.11, 8.14 | `seo-images` |
| AI crawler access, citability, entity clarity, brand signals | 5, 6.4, 9 | `seo-geo` |
| `llms.txt`, Markdown delivery, agent-facing discovery files, AI-agent rules in `robots.txt`, WAF treatment of crawlers and agents | 6.3, 6.4, 9.5 | `seo-agentic` |
| Backlink profile, gaps, unlinked mentions | 10.2 | `seo-backlinks` |
| Baselines and regression detection between deploys | 8.9, 13.3 | `seo-drift` |
| Search Console, PageSpeed, CrUX, Indexing API, GA4 | 12.2 | `seo-google` |
| Roadmap, site architecture, content calendar | 4, 14 | `seo-plan` |
| Evidence-led prompts by stage (find, leverage, optimize, win) | 14 | `seo-flow` |
| When the domain is SEO but the right workflow is unclear | — | `seo` |

### 17.2 Extension skills that need credentials

These skills are installed but do nothing until their service is configured with
an API key. Each covers a part of section 12 that the core skills cannot.

| Skill | Covers | Sections |
|---|---|---|
| `seo-bing` | Bing Webmaster Tools, IndexNow submission, Copilot citation data | 6.6, 12.2 |
| `seo-seranking` | AI share of voice across ChatGPT, Gemini, Perplexity, AI Overviews, AI Mode | 12.3, 12.4 |
| `seo-profound` | Time series of brand citation rates in AI systems | 12.3–12.5 |
| `seo-dataforseo` | Live SERP, keyword volume, backlinks, AI mention tracking | 8.2, 10.2, 12.6 |
| `seo-ahrefs` | Referring domains, backlinks, organic keywords | 10.2, 12.6 |
| `seo-firecrawl` | Full-site crawl, site map, broken links | 6.1, 8.6 |
| `seo-unlighthouse` | Lighthouse across many pages, run locally | 6.10 |
| `seo-matomo` | Self-hosted analytics as an alternative to GA4 | 12.2 |
| `seo-image-gen` | Open Graph and hero images | 8.3, 8.11 |

Not applicable to Shosai: `seo-local`, `seo-maps` (no physical locations) and
`seo-ecommerce` (no product catalog).

### 17.3 When to run what

| Moment | Action |
|---|---|
| Planning a new public page | `seo-sxo` for intent, then `seo-content-brief`. |
| Before a public page ships | `seo-page` on the page; `seo-schema` if it carries JSON-LD; `seo-hreflang` if it has locale variants. |
| Before a release that touches public pages | `seo-drift` against the stored baseline. |
| After a production deploy | `seo-technical` on the smoke set from 13.3, then IndexNow. |
| Weekly | `seo-geo` plus the monitoring extensions for the query matrix in 12.3. |
| Quarterly | `seo-audit` for the full site; `seo-backlinks` for authority. |

### 17.4 Limits of the tooling

- **The runtime is not set up yet.** Skills that run bundled scripts (page
  fetching, rendering, screenshots, Google reports) need
  `.claude/skills/seo/scripts/claude-seo setup` to be run once.
- **Yandex is not covered.** Section 12.2 tracks Yandex, but no `claude-seo`
  skill reads Yandex Webmaster. That data needs a separate source.
- **Business metrics are outside `claude-seo`.** Revenue attribution (11.3), the
  search data store (12.8) and conversion tracking are product analytics and must
  be built in Shosai itself.
- **CI gates are not provided.** The skills audit on demand. The hard and soft
  gates in 13.2 must be implemented as checks in the project's CI pipeline.
- **Audit output is evidence, not a verdict.** A skill's score is an input to the
  scorecard in 12.9, which deliberately has no single number.

---

## 18. Open decisions

These points are unresolved or conflict with other project rules. Each needs a
decision before the related part of the strategy is built.

### 18.1 Rendering of public pages conflicts with the project stack

Phase 1 and sections 6.7 and 6.9 require server-rendered or statically generated
public pages and real `404` responses. The project stack is React with Vite, a
client-rendered single-page app, with no server rendering. A single-page app
serves one HTML shell for every URL, which is exactly the soft 404 that 6.7
forbids.

**Resolved on 2026-10-07** by [ADR 0021](../adr/0021-public-site-on-nextjs-cabinet-on-vite.md):
public pages live in a separate public site on Next.js (`site/`), server-rendered
or statically generated; the cabinet stays a Vite single-page app outside the
indexable inventory. The site must give each public page its own path URL (6.2), let the server decide
the status (6.7), put the head elements in the server response (6.9) and take
the origin from configuration (6.12).

### 18.2 Hard gates: two source lists

The strategy draft says CI must fail on thirteen conditions. The later
recommendation names four hard failures and three soft warnings. Section 13.2
keeps all thirteen deterministic errors as hard gates and adds the four from the
recommendation, because every one of them is an objective correctness error and
none appears in the soft list. Confirm or narrow.

The gates for Open Graph, fragment routing, the production origin,
non-production exposure and crawler access are not a third source list. They
make the P0 rules of section 6 and the page rules of 8.3 checkable, and they
fail only on deterministic errors.

### 18.3 "Closed benchmark" versus public methodology

The phase 2 recommendation speaks of publishing a first "closed" benchmark.
Section 9.4 requires public methodology and raw data, and the kill list forbids
unverifiable statistics. This document assumes the benchmark is public with
public methodology. If "closed" meant something else, it must be reconciled with
9.4.

### 18.4 Community "seeding" versus the usefulness rule

The phase 2 recommendation speaks of seeding discussions on Reddit and Hacker
News. Section 10.3 requires usefulness first, and 15.3 forbids automated spam.
This document words phase 2 as participation. Coordinated posting that hides its
connection to Shosai would break both rules and both communities' own rules.

### 18.5 "Always first" cannot be a requirement

The no-bot recommendation aims for Shosai to always be listed first in the
bot-free category. Placement in an AI answer cannot be guaranteed, and section 1
rejects ranking by gaming. Section 5.3 sets the controllable requirement: state
the differentiator consistently and truthfully everywhere.

### 18.6 The differentiator must match the rewritten product

Sections 5.3 and 9.2 describe local capture of microphone and system audio
without a meeting bot. `shosai` is a rewrite. The claim is published only
after the rewritten product is confirmed to work this way.

### 18.7 Product category: workspace or meeting assistant

Section 5.1 defines the entity as an AI Workspace. Most target queries in 8.5 and
12.3 are about meeting assistants. Section 5.2 warns against exactly this kind
of split identity. A single category statement is needed that serves both, for
example "an AI workspace whose core capability is meetings".

### 18.8 Monitoring needs paid services

Daily or weekly AI visibility monitoring (12.3) and backlink data (10.2) depend
on the extension skills in 17.2, each of which needs a paid account. Which
services are used is undecided.

### 18.9 Where search data lives

Section 12.8 requires a logically separate store for search data. The project
stack names PostgreSQL as the source of truth but defines no analytics store.

### 18.10 Platform claims must be re-verified

The strategy cites behavior of third parties: Google's scaled content abuse
policy and preferred sources, Bing's AI Performance report and its sitemap and
IndexNow guidance, OpenAI's and Anthropic's crawler roles, the end of FAQ and
HowTo rich results, Search Console's generative AI report, the image size and
robots directive that Discover needs, X's fallback to Open Graph, and the
`utm_source` values AI assistants add. These change. Check the current
official documentation before relying on any of them.

### 18.11 Privacy and legal review

Sections 11.2 and 11.4 use product usage data for research. This needs a privacy
and legal review before any such data is published, even aggregated.

Web analytics and attribution on public pages (11.3: funnel events, the first
touch carried into the client, the AI channel) need the same review: consent,
cookies and cross-border transfer under the law of each market. So do the legal
details on the trust pages (8.13). The site loads the cabinet's Google Tag Manager
container under the same rules: Consent Mode v2 denied until the visitor
accepts, the site's banner as the one place that asks (the cabinet does not),
one consent cookie shared with the cabinet, and only the tags its list allows ([ADR 0045](../adr/0045-google-tag-manager-behind-consent.md)).

### 18.12 Visual parity with the draft versus new page rules

The rewrite must show no visual difference from the draft (project rules).
Several rules here change what a page shows: author bylines and profiles and the
trust pages with their footer links (8.13), visible dates (8.10), figure
captions (8.14), breadcrumbs (8.12). Invisible rules do not touch parity: head
metadata, structured data, status codes, redirects, headers, sitemaps.

**Resolved on 2026-10-07** by [ADR 0022](../adr/0022-new-web-design-replaces-draft-parity.md):
visual parity with the draft is no longer a goal, so S17 ships the visible and
the invisible rules together.

### 18.13 Definition of the first useful action

The funnel (2.2) and its events (11.3) need one definition of the first useful
action, for example a first transcribed meeting or a first answer from Leo. It is
a product decision. Until it is made, search reports end at signup.

---

## 19. Final SEO/GEO/AIO Coverage

"Covered" means that every rule of the area is stated, has a priority and has a
check. It does not mean built: S17 builds the public site against this document.

| Area | Status | Where |
|---|---|---|
| Technical SEO | Covered | 6, 13.2–13.4 |
| On-page SEO | Covered | 8.3, 8.10, 8.12, 8.14 |
| Entity SEO | Covered; the category statement is open (18.7) | 5, 7 |
| E-E-A-T and trust | Covered | 8.3, 8.13, 9.2, 9.4 |
| GEO | Covered | 9 |
| AIO measurement | Rules covered; data needs paid services (18.8) | 12.1, 12.3–12.6 |
| Multimodal | Covered | 8.11, 8.14 |
| International | Rules covered; languages beyond English wait for phase 3 (4) | 6.8, 7 |
| Analytics and attribution | Rules covered; storage (18.9), activation (18.13) and privacy review (18.11) are open | 11.3, 12 |
| Security and infrastructure | Covered | 6.3, 6.11, 6.12, 13 |
| Content lifecycle | Covered | 6.7, 8.8–8.10 |
| CRO | Rules covered; activation is open (18.13) | 2.2, 11 |

Deliberately deferred:

- **Phases 2 and 3** (4): the benchmark, community work, languages beyond
  English and programmatic SEO.
- **Yandex data** (17.4): no tool reads it yet.
- **`llms.txt` and other machine-readable experiments** stay P3 (9.5).
- **Not applicable:** local SEO, maps and e-commerce (17.2).

---

## Appendix A. Map of original sections

The original draft had 118 numbered sections. This table shows where each one
went.

| Original | Here | Original | Here |
|---|---|---|---|
| S0 Search strategy | 2 | S60 SERP gap analysis | 12.6 |
| S1 Priority system | 3 | S61–S62 Image, video | 8.11, 8.14 |
| S2 SEO architecture | 6.1, 6.12 | S63 Performance | 6.10 |
| S3 URL architecture | 6.2 | S64 Web architecture | 6.9 |
| S4 Crawlability | 6.3 | S65 Security | 6.11 |
| S5 Robots.txt | 6.4 | S66 Observability | 12.7 |
| S6 XML sitemap | 6.5 | S67 Automated QA | 13.2 |
| S7 IndexNow | 6.6, 6.12 | S68 Regression tests | 13.3 |
| S8–S9 Status, canonical | 6.7 | S69 Deployment pipeline | 13.4 |
| S10 Hreflang | 6.8 | S70 Incident response | 13.5 |
| S11 International | 7 | S71 Search Console | 12.2 |
| S12 On-page | 8.3 | S72 AI monitoring | 12.3 |
| S13 Search intent | 8.1 | S73 AI regression | 12.5 |
| S14–S15 SERP, information gain | 8.2 | S74 Knowledge graph | 5.4 |
| S16 Topical authority | 8.5 | S75 Knowledge consistency | 5.2 |
| S17 Internal linking | 8.6 | S76 Product-led SEO | 11.1 |
| S18–S19 Entity | 5.1, 5.2 | S77–S78 Free tools, assets | 11.2 |
| S20–S21 Structured data | 8.12 | S79 Search-to-product bridge | 11.1 |
| S22 GEO | 9 | S80–S81 First-party data | 11.4 |
| S23 LLM-readable content | 9.1 | S82–S83 PR, community | 10.3 |
| S24 Citation engineering | 9.2 | S84 Founder entity | 5.5 |
| S25 Citation units | 9.3 | S85–S89 Docs, help, glossary, comparison, alternatives | 8.11 |
| S26 Evidence architecture | 9.2 | S90–S91 Reviews, reputation | 10.4 |
| S27–S28 Research, benchmarks | 9.4 | S92 Content trust | 8.3, 8.13 |
| S29 AI search optimization | 12.1 | S93–S95 Freshness, dates | 8.10 |
| S30–S31 AI dataset, query matrix | 12.3 | S96 Data warehouse | 12.8 |
| S32 Citation monitoring | 12.4 | S97 Query → revenue | 2.2, 11.3 |
| S33–S34 Accuracy, hallucinations | 9.6 | S98–S99 North star, quality score | 12.9 |
| S35 Machine-readable layer | 9.5 | S100 Governance | 13.1 |
| S36 AI crawler policy | 6.4 | S101 Kill list | 15.3 |
| S37 AIO | 2.1, 12.1 | S102–S103 Quality principles | 15.1, 15.2 |
| S38–S39 Brand SEO | 10.1 | S104 Entity principle | 5.1 |
| S40–S43 Off-page, links | 10.2 | S105 AIO principle | 12.4 |
| S44–S46 Programmatic SEO | 8.7 | S106 Preferred sources | 12.1 |
| S47 Cannibalization | 8.8 | S107 Surface expansion | 12.1 |
| S48–S50 Decay, refresh, lifecycle | 8.9 | S108–S110 Cadence | 14 |
| S51 Content brief | 8.4 | S111–S112 Moat, flywheel | 11.4 |
| S52 Content types | 8.11 | S113 Final architecture | 2.1 |
| S53 Template SEO | 8.11 | S114 Ultimate principle | 1 |
| S54 Conversion SEO | 2.2 | S115 Definition of done | 13.6 |
| S55 Revenue attribution | 11.3 | S116 Commandments | 15.4 |
| S56 SEO analytics | 12.2 | S117 Ultimate KPI | 16 |
| S57 AI analytics | 12.4 | S118 Strategic objective | 16 |
| S58–S59 Share of voice, competitors | 12.6 | Recommendations 1–3 | 4, 5.3, 13.2 |
