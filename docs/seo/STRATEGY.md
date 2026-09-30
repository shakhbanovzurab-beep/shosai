# Whisperer Search Strategy: SEO, GEO and AIO

This document defines how Whisperer becomes visible, correctly understood and
cited in search engines and AI answer systems, and how that visibility turns
into activation and revenue. It describes the target state for `whisperer-v2`.

- **Audience:** engineers and coding agents who build or change any public
  Whisperer page, and whoever plans content.
- **Tooling:** the `claude-seo` skills installed in `.claude/skills/`. Section 17
  maps every part of this strategy to the skill that executes or checks it.
- **Canonical domain:** `whisperer.one`.
- **Status:** strategy, not implementation. Section 18 lists the decisions that
  must be made before it can be built.

Numbers in brackets such as `[S24]` point to the section of the original
strategy draft that the text comes from. Appendix A lists them all.

---

## 1. Goal and principle

**Goal.** Make Whisperer the most visible and most trusted source for its target
search and AI queries: error-free indexing, dominant topical coverage, a strong
entity graph, high citation rates in AI systems, and the highest possible
conversion of organic demand into activation and revenue.

**Principle.** Do not optimize the site for search engines. Optimize the
**Whisperer knowledge system** so that a search engine, an AI system and a person
all get the same precise answer to six questions:

1. What is Whisperer?
2. What problem does it solve?
3. Who is it for?
4. How does it work?
5. How is it different, and what are its limits?
6. Where is that proven?

Whisperer should not try to rank first by gaming an algorithm. It should be so
useful, specific, original, trusted, well structured, well linked, well
understood, well cited and technically accessible that choosing it as the
relevant source is the easiest option for a search engine or an AI system. `[S114]`

---

## 2. The model

### 2.1 Five layers `[S0]`

| Layer | What it is responsible for |
|---|---|
| **SEO** | Pages are discovered and ranked. |
| **GEO** (generative engine optimization) | Whisperer's information is likely to appear in generated answers. |
| **AIO** (AI optimization) | Presence in AI-powered search. AIO = SEO + GEO + entity + citation + AI search monitoring. `[S37]` |
| **Entity SEO** | Whisperer is one unambiguous entity. |
| **CRO** (conversion rate optimization) | Organic attention becomes installs, activation and money. |

### 2.2 The funnel `[S0, S54, S97]`

```text
Query → SERP or AI answer → Whisperer citation or mention
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
Whisperer
  type:   AI Workspace / SoftwareApplication
  domain: whisperer.one
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

Do not let these read as four different products: "Whisperer AI",
"Whisperer.one", "Whisperer Workspace", "Whisperer Meeting Assistant".

If one source says "Whisperer is a meeting bot" and another says "Whisperer is a
local AI workspace", entity ambiguity grows and AI answers get worse.

### 5.3 The main differentiator: no-bot architecture

AI systems comparing meeting assistants usually sort them into two groups: bots
that join the call, and tools that capture audio locally. Whisperer states its
group explicitly in every short definition on the site (the citation units in
9.3), so that it is placed in the privacy-first, bot-free category.

This is a factual claim and follows the evidence rule in 9.2: it is published
only in the form the product actually implements, and it is updated when the
product changes.

### 5.4 Knowledge graph `[S74]`

Build one graph in which Whisperer links to: SoftwareApplication, AI Workspace,
Leo, Meeting Assistant, Transcription, Translation, MCP, Founder, GitHub,
Documentation, social profiles and external references. The same entity always
has the same identifier and the same description.

### 5.5 Founder entity `[S84]`

Maintain one consistent public founder profile that connects
Founder → Whisperer → GitHub → technical writing → research → interviews. This
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

### 6.3 Crawlability `[S4]`

Verify access for: Googlebot, Bingbot, OAI-SearchBot, ChatGPT-User, ClaudeBot,
PerplexityBot, Applebot, Amazonbot, Common Crawl and any other relevant crawler.

For each crawler record: crawler, URL, timestamp, HTTP status, response time,
robots decision, content type, content length, canonical, indexability.

Look specifically for blocks caused by: WAF, rate limiting, CDN, firewall, bot
protection, accidental `403`, JavaScript challenges, CAPTCHA, geo blocking.

`OAI-SearchBot` is critical: blocking it removes the site from ChatGPT Search
results.

### 6.4 `robots.txt` and AI crawler policy `[S5, S36]`

Define a separate policy for each of four access types:

| Access type | Example crawler |
|---|---|
| Search | Googlebot, Bingbot, `OAI-SearchBot`, PerplexityBot |
| Training | `GPTBot`, ClaudeBot |
| User-triggered browsing | `ChatGPT-User` |
| Private application and ads validation | decided per case |

`OAI-SearchBot` is not `GPTBot`. The first feeds search; the second crawls for
model training. Never block an AI search crawler by accident.

### 6.5 XML sitemap `[S6]`

**P0.** A sitemap contains only URLs that are canonical, indexable, return HTTP
200 and are real public pages.

Check: URL count, duplicates, `3xx`, `4xx`, `5xx`, `noindex`, canonical mismatch,
hreflang mismatch, stale `lastmod`.

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

**Never** submit a production-domain URL from a development environment.

IndexNow notifies search engines of a change. It does not guarantee indexing.

### 6.7 HTTP status and canonical `[S8, S9]`

| Status | Meaning |
|---|---|
| `200` | Valid page |
| `301` / `308` | Permanent redirect |
| `404` | Resource does not exist |
| `410` | Resource intentionally removed |
| `403` | Access restricted |
| `429` | Rate limited |
| `500` | Server failure |

**Soft 404 is forbidden.** An unknown public URL must return a real `404`, not
the single-page-app shell with `200`.

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

Phase 1 requires server-side rendering or static generation for public pages.
How this is reached with the project stack is an open decision (18.1).

### 6.10 Performance `[S63]`

Track: TTFB, LCP, INP, CLS, FCP, server response time, JavaScript execution,
CSS, fonts, images, cache, compression.

Target: a fast server, a small critical payload, a stable layout and minimal
blocking JavaScript.

### 6.11 Security `[S65]`

Security infrastructure must not break crawler access. Check: TLS, certificates,
CSP, WAF, rate limits, bot rules, redirects, security headers. A legitimate
crawler is not a malicious bot and must not be treated as one.

---

## 7. International SEO `[S11]`

Translation is not localization. Each language gets its own: keyword research,
search intent, slug, title, meta description, headings, terminology, examples,
FAQ, call to action, pricing, screenshots, competitors, backlinks, directories,
SERP analysis and AI queries.

Each market has its own chain: query → intent → SERP → content → entity → call
to action.

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

Detect automatically when one query ranks several Whisperer URLs. When that
happens, choose one of: merge, redirect, canonicalize, differentiate the intent,
or change the internal link architecture.

### 8.9 Lifecycle, decay and refresh `[S48, S49, S50]`

Lifecycle: research → brief → production → technical validation → publish →
IndexNow → index monitoring → ranking monitoring → conversion monitoring →
refresh → consolidate or delete.

Each page tracks: `last_updated`, traffic over 30 and 90 days, impressions, CTR,
ranking, backlinks, AI citations, conversion.

Decay signals: traffic, rank, CTR or AI citations fall; competitor coverage
grows; the SERP changes; facts go out of date.

Never update a page only to change its date. A refresh means new data, examples,
screenshots, sources, benchmarks or sections, corrected facts, or changed product
capabilities.

### 8.10 Freshness and dates `[S93, S94, S95]`

Detect automatically the pages affected when any of these change: pricing,
features, integrations, product behavior, supported languages, benchmarks,
screenshots. A page must never mix pricing from one year with the product of
another.

Store on every page: `published_at`, `updated_at`, `reviewed_at`,
`product_version`. For research also: `dataset_version`, `model_version`,
`test_date`, `environment`.

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
| **Glossary** `[S87]` | Authoritative definitions of terms such as AI meeting assistant, meeting transcription, speaker diarization, real-time translation, AI workspace, MCP, AI agent, meeting protocol, action item. Each entry: definition, examples, related concepts, and how Whisperer implements it where relevant. |
| **Comparison** `[S88]` | Whisperer versus Granola, Otter, Fireflies, Fathom. Factual, current, sourced, date-stamped, feature by feature. Never a page whose only purpose is to say Whisperer is better. |
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
rich result or a higher position.

CI validates: valid JSON, schema validity, required properties, URL validity,
`@id`, consistency with canonical, entity references, duplicate entities, stale
data. Pipeline: generate → validate → build → deploy → crawl smoke test.

---

## 9. GEO: being cited by AI systems

GEO is not "writing text for ChatGPT". The task is to make Whisperer's
information understandable, verifiable, citable and unambiguously tied to the
Whisperer entity. `[S22]`

### 9.1 Direct answers `[S23]`

The first screen of every key page quickly answers: what is Whisperer, who is it
for, what does it do, how does it work, what makes it different.

Use concise definitions, factual claims, structured lists, tables, dates,
numbers, explicit entities and explicit relationships.

### 9.2 Citation engineering `[S24, S26]`

Write claims as: claim + entity + specific fact + context + date + evidence.

- **Weak:** "Whisperer makes meetings smarter."
- **Strong:** "Whisperer records the microphone and system audio on the user's
  device without a meeting bot. After the meeting, Leo can extract decisions,
  commitments, risks and open questions."

Every important claim is specific, verifiable, attributable, current and
self-contained.

Strong claims carry a full chain: claim → evidence → source → methodology →
date. This applies especially to benchmarks, latency, accuracy, pricing, market
statistics, feature comparisons, performance, security and infrastructure.

### 9.3 Citation units `[S25]`

Create blocks that can be quoted on their own: definition, fact, statistic,
methodology, result, comparison, limitation, example. Do not bury an important
fact inside five paragraphs of marketing copy.

### 9.4 Original research and benchmarks `[S27, S28]`

Whisperer becomes a source of data, not only a product. Publish: transcription
benchmarks, translation latency tests, meeting-AI benchmarks, model evaluations,
multilingual evaluations, meeting workflow experiments, AI assistant benchmarks,
productivity experiments, cost comparisons.

Each study states: question, methodology, dataset, environment, variables,
results, limitations, raw data, conclusion, date.

Example: "AI Meeting Assistant Benchmark 2026", comparing latency, transcription
accuracy, speaker diarization, translation latency, language coverage,
hallucination rate, action-item extraction, summary quality, cost and privacy
model. **The methodology is public.**

### 9.5 Machine-readable layer `[S35]`

Whisperer may serve `/llms.txt` and `/llms-full.txt`. Treat them as an
additional machine-readable interface, not as a proven ranking factor (P3).

The layer covers product, features, pricing, documentation, security,
limitations, FAQ, API, MCP and changelog, and must never contradict the website,
documentation, social profiles or directories.

### 9.6 Answer accuracy and hallucination defense `[S33, S34]`

Run an automated audit: expected fact → AI answer → diff → correct, missing or
incorrect. Check: name, category, features, pricing, languages, platforms,
privacy, bot or no bot, Leo, MCP, limitations.

When an AI system describes Whisperer wrongly:

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

Brand query set: `whisperer`, `whisperer ai`, `whisperer.one`,
`whisperer workspace`, `whisperer meetings`, `whisperer leo`,
`whisperer transcription`, `whisperer translation`, `whisperer mcp`.

Monitor: SERP, sitelinks, knowledge and entity signals, branded snippets, AI
mentions, incorrect descriptions, competitors intercepting brand queries.

Aim to control the first page for branded queries through: the official website,
documentation, GitHub, social profiles, product directories, reviews, articles,
interviews, Product Hunt, G2, AlternativeTo, StackShare and relevant communities.

### 10.2 Links `[S40, S41, S42, S43]`

Principle: do not buy many links. Build a network of independent confirmations
that Whisperer exists and is authoritative.

Priority order for a link: topical relevance, editorial placement, trust,
traffic, uniqueness, authority.

Sources: technical publications, SaaS and AI directories, startup databases,
GitHub, Product Hunt, G2, AlternativeTo, StackShare, founder interviews,
podcasts, YouTube, research publications, benchmark references, guest articles,
digital PR, citations of original research.

Linkable assets to create: benchmarks, datasets, calculators, templates,
reports, original research, statistics, engineering articles, open-source tools,
documentation, glossaries, comparison databases.

Unlinked mentions: search regularly for "Whisperer", "whisperer.one" and
"Whisperer AI"; for each mention check context, authority and whether a link
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

Monitor "Whisperer", "Whisperer AI", "whisperer.one" and "Leo" across search, AI
systems, Reddit, GitHub, directories and review platforms. Correct errors through
authoritative sources.

---

## 11. Product-led search and conversion

### 11.1 Bridge from search to product `[S76, S79]`

Every SEO asset has a logical bridge: search problem → useful solution →
Whisperer → download → activation. An article that ends at a generic homepage is
not acceptable.

Examples: meeting protocol template → download → Whisperer; meeting
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
value → optional Whisperer call to action.

### 11.3 Revenue attribution `[S55, S97]`

Minimum dimensions: query, landing page, cluster, country, language, device,
source, medium, campaign, signup, activation, subscription, revenue.

Report revenue per organic landing page, per cluster, per country and per
language. The goal is not maximum traffic but high-intent organic revenue.

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

---

## 12. Measurement

### 12.1 Search surfaces `[S29, S107]`

Track presence on: Google Search, Google AI Overviews, Google AI Mode, Google
Discover, Bing, Copilot, ChatGPT Search, Perplexity, Gemini, YouTube, Reddit,
GitHub and product directories. Whisperer should be present wherever discovery
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

### 12.3 AI visibility dataset `[S30, S31, S72]`

Each day or week: run the priority queries against the AI engines, capture the
answer, extract mentions and citations, compare with the previous run, and store
the result with history.

Record per observation: query, country, language, date, engine, model or
surface, whether Whisperer was mentioned, whether it was cited, citation URL,
citation position, competitors, features attributed, errors, sentiment and
context.

Minimum query matrix:

| Category | Example queries |
|---|---|
| Generic | best AI meeting assistant, AI meeting assistant, meeting transcription software, AI meeting notes, AI meeting summary |
| Differentiation | AI meeting assistant without bot, meeting assistant without Zoom bot, local meeting transcription, privacy-focused meeting assistant |
| Product | Whisperer AI, Whisperer AI Workspace, Whisperer Leo, Whisperer meeting assistant |
| Comparison | Granola alternatives, Otter alternatives, AI meeting assistant alternatives |
| Use case | AI for interviews, for meetings, for sales meetings, for product meetings, for developers |
| Translation | real-time meeting translation, AI call translation, meeting translator, live speech translation |

### 12.4 AI metrics `[S32, S57, S105]`

Mention rate, citation rate, citation share, unique cited URLs, query coverage,
entity accuracy, feature accuracy, competitor share of voice, AI traffic,
AI-assisted conversion.

An AI citation is a visibility signal. It is not a click and not a conversion.

"ChatGPT mentioned Whisperer" is not a measurement. A measurement combines
mention, citation, correctness, query relevance, competitor context and
conversion.

### 12.5 AI visibility regression `[S73]`

When the citation rate falls, check: content freshness, entity consistency,
crawlability, competitors being cited instead, SERP changes, source quality,
query demand, AI model changes. A fall in citation rate is not automatically an
SEO penalty.

### 12.6 Share of voice and competitors `[S58, S59, S60]`

For each priority cluster: Whisperer visibility divided by total relevant
visibility, counted separately for Google, Bing, AI search, branded and
non-branded queries.

Competitors to track: Granola, Otter, Fireflies, Fathom, Notta, Wispr, Parakeet
and any other real SERP competitor. Compare not only domains but queries, pages,
entities, backlinks, topics, features, citations, AI mentions and content gaps.

For each priority query compare Whisperer with the top 10 on: content depth,
unique information, backlinks, domain authority, entities, freshness, UX, intent
satisfaction, structured data, internal links and AI citations.

### 12.7 Crawler telemetry `[S66]`

Log per request: crawler, URL, status, latency, bytes, cache, robots decision,
canonical, indexability. Dashboard by crawler: Googlebot, Bingbot,
OAI-SearchBot, ClaudeBot, PerplexityBot.

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

**Hard gates — the build fails.** These are deterministic correctness errors:

- broken or duplicate canonical
- `noindex` on a production page that must be indexed
- a `404` URL inside the sitemap or hreflang; invalid hreflang; broken sitemap
- JSON-LD syntax or schema error
- wrong HTTP status, soft 404
- broken internal link
- missing or duplicate title, missing H1, missing `lang`
- invalid `robots.txt`

**Soft gates — a warning, the build passes:**

- missing external citations
- delayed metric updates
- missing translation in a rare locale

### 13.3 Regression tests on every deploy `[S68]`

Check on critical URLs: canonical, robots, sitemap, hreflang, schema, status,
redirects, metadata.

Minimum smoke set: homepage, pricing, product, documentation, blog, each
published language, each important cluster.

### 13.4 Deployment pipeline `[S69]`

```text
code → SEO validation → content validation → schema validation
→ sitemap generation → hreflang validation → build → deploy
→ production smoke test → HTTP verification → IndexNow → monitoring
```

IndexNow is always the last step, after production deployment.

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
- [ ] Title, meta description and H1 validated
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

| When someone… | Whisperer… |
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
architecture for Whisperer.

---

## 17. Executing the strategy with `claude-seo`

The `claude-seo` skills in `.claude/skills/` are the working tools for this
strategy. Use the skill named here rather than improvising the analysis.

### 17.1 Strategy area → skill

| Strategy area | Sections | Skill |
|---|---|---|
| Full-site audit, scored and prioritized | 6, 13 | `seo-audit` |
| One URL, all aspects | 8.3 | `seo-page` |
| Crawlability, indexability, status codes, canonical, redirects, rendering, Core Web Vitals, IndexNow, security headers | 6.1–6.3, 6.6, 6.7, 6.9–6.11 | `seo-technical` |
| Sitemap validation and generation | 6.5 | `seo-sitemap` |
| Hreflang and international setup | 6.8, 7 | `seo-hreflang` |
| JSON-LD detection, validation, generation | 8.12 | `seo-schema` |
| Content quality, E-E-A-T, citation readiness | 8.3, 9.1–9.3 | `seo-content` |
| Content briefs | 8.4 | `seo-content-brief` |
| Topical clusters and internal link architecture | 8.5, 8.6 | `seo-cluster` |
| Intent and page-type mismatch against the SERP | 8.1, 8.2 | `seo-sxo` |
| Programmatic SEO planning and thin-content safeguards | 8.7, 8.8 | `seo-programmatic` |
| Comparison and alternatives pages | 8.11 | `seo-competitor-pages` |
| Image optimization | 8.11 | `seo-images` |
| AI crawler access, citability, entity clarity, brand signals | 5, 6.4, 9 | `seo-geo` |
| `llms.txt`, Markdown delivery, agent-facing discovery files, AI-agent rules in `robots.txt` | 6.4, 9.5 | `seo-agentic` |
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
| `seo-image-gen` | Open Graph and hero images | 8.11 |

Not applicable to Whisperer: `seo-local`, `seo-maps` (no physical locations) and
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
  be built in Whisperer itself.
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

A decision is needed on how public pages are produced: static generation for the
public site, server rendering, or a separate public site next to the application.
This is an architectural decision and belongs in an ADR.

### 18.2 Hard gates: two source lists

The strategy draft says CI must fail on thirteen conditions. The later
recommendation names four hard failures and three soft warnings. Section 13.2
keeps all thirteen deterministic errors as hard gates and adds the four from the
recommendation, because every one of them is an objective correctness error and
none appears in the soft list. Confirm or narrow.

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
connection to Whisperer would break both rules and both communities' own rules.

### 18.5 "Always first" cannot be a requirement

The no-bot recommendation aims for Whisperer to always be listed first in the
bot-free category. Placement in an AI answer cannot be guaranteed, and section 1
rejects ranking by gaming. Section 5.3 sets the controllable requirement: state
the differentiator consistently and truthfully everywhere.

### 18.6 The differentiator must match the rewritten product

Sections 5.3 and 9.2 describe local capture of microphone and system audio
without a meeting bot. `whisperer-v2` is a rewrite. The claim is published only
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
IndexNow guidance, OpenAI's crawler roles. These change. Check the current
official documentation before relying on any of them.

### 18.11 Privacy and legal review

Sections 11.2 and 11.4 use product usage data for research. This needs a privacy
and legal review before any such data is published, even aggregated.

---

## Appendix A. Map of original sections

The original draft had 118 numbered sections. This table shows where each one
went.

| Original | Here | Original | Here |
|---|---|---|---|
| S0 Search strategy | 2 | S60 SERP gap analysis | 12.6 |
| S1 Priority system | 3 | S61–S62 Image, video | 8.11 |
| S2 SEO architecture | 6.1 | S63 Performance | 6.10 |
| S3 URL architecture | 6.2 | S64 Web architecture | 6.9 |
| S4 Crawlability | 6.3 | S65 Security | 6.11 |
| S5 Robots.txt | 6.4 | S66 Observability | 12.7 |
| S6 XML sitemap | 6.5 | S67 Automated QA | 13.2 |
| S7 IndexNow | 6.6 | S68 Regression tests | 13.3 |
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
| S27–S28 Research, benchmarks | 9.4 | S92 Content trust | 8.3 |
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
