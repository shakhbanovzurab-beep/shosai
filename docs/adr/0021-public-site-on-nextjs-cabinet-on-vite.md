# ADR 0021 — Public site on Next.js, cabinet on a Vite SPA, backend only on FastAPI

- **Status:** accepted by the owner on 2026-10-07.
- **Packages:** F2 (cabinet), S17 (public site); every slice with public or shared pages.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.2, §5, §18, §19; [SEO strategy](../seo/STRATEGY.md) 6.2, 6.7, 6.9, 6.12, 18.1; [ADR 0022](0022-new-web-design-replaces-draft-parity.md); [CLAUDE.md](../../.claude/CLAUDE.md) "Undecided".

## Context

- The SEO strategy requires server-rendered or statically generated public pages: their own path URLs, the status decided by the server, real `404` responses, head metadata and Open Graph in the first response (6.2, 6.7, 6.9). A single-page app serves one shell for every URL, which is the soft 404 that 6.7 forbids. How public pages are produced was open (SEO 18.1, CLAUDE.md "Undecided"; S17 was to decide).
- The draft serves its landing as pre-built static HTML from the backend (`web_landing*.py`, `static/landing/`) and builds server-side preview pages for links that people forward (`web_share.py`, used by meeting results and broadcasts), because messenger previews read only the `<head>` of the first response and run no JavaScript.
- The signed-in cabinet is an application, not an indexable page set (SEO 6.12). It needs no server rendering; the target architecture already makes it a client-rendered SPA and PWA on Vite (§4.2, §18.1).
- On 2026-10-07 the owner committed a new web UI (`f4f8430`) built on Next.js 16. All its 50 pages belong to the cabinet and the administration; about 320 files under `src/app/api/`, `src/server/` and `features/*/server/` are a sample backend with seeded in-memory data.
- The new UI translates through `next-intl` (≈ 430 imports, ICU messages in 16 languages). §18.2 named i18next, which has a different call shape and message format.

## Decision

1. **Two web applications, one origin.**
   - **Public site** — landing, blog, documentation, pricing, legal pages, the help centre, and public pages of shared links (`/s/<token>` and the draft's forwarded meeting and broadcast addresses). **Next.js**, latest stable, in `site/` of this repository. Pages are server-rendered or statically generated.
   - **Cabinet** — the signed-in application: dashboard, meetings, notes, knowledge base, tasks, calendar, files, Leo, settings and the administration. **Vite SPA**, latest stable, in `frontend/`, served as static files by the edge. It stays installable as a PWA.
2. **The backend is FastAPI only.** Neither web application owns an API, a database connection, a queue or a secret beyond its own configuration. The Next.js process renders pages; the data it renders comes from the FastAPI `/v1` API, server to server inside the plane. No route handler, server action or middleware of Next.js holds business logic.
3. **Edge routing on `whisperer.one`.** `/v1/ws/*` → WS gateway and `/v1/*` → API, as before. The cabinet's paths (`/app/*`, `/admin/*`, the OAuth callback, `/unauthorized` — added by F2-D5 on 2026-10-08) → the SPA's static files with its `index.html` as the fallback for its own routes only. Every other path → the public site, which answers `404` for a path that matches no page.
4. **Not indexable.** The cabinet sends `X-Robots-Tag: noindex` and is absent from the sitemap; `sitemap.xml`, `robots.txt` and the Open Graph images belong to the public site.
5. **One translation system.** The cabinet uses `use-intl`, the framework-agnostic core of `next-intl`; the public site uses `next-intl`. Both read ICU messages in the 16 platform languages. i18next and react-i18next leave §18.2.
6. **Router and data.** The cabinet keeps §18.2: React Router for routing and TanStack Query for server state. Its response types are generated from the OpenAPI contract of the backend.
7. **Links already issued keep working.** Every forwarded address the draft has issued (meeting results, broadcasts, public files) resolves on the public site, directly or with one `301` to its new form. The slice that owns the resource lists its addresses; S17 serves them.
8. **The sample backend in `frontend/` is removed** when the cabinet moves to Vite; its screens read the FastAPI API.

## Alternatives considered

| Option | Why not |
|---|---|
| Everything on Next.js, cabinet included | A second server process on the request path of every cabinet screen; server rendering the cabinet does not need; server components and route handlers invite business logic outside FastAPI, which §5 and contract-first forbid |
| Everything on the Vite SPA, public pages pre-rendered at build | Pre-rendering covers static pages but not shared-link previews with per-link titles and images, or `404` for an unknown token; the blog and documentation would need a hand-made static generator |
| Public pages rendered by FastAPI, as the draft does | Templates outside React duplicate the design system; the draft's experience (a separate static landing build) is what the owner chose to replace |
| Keep i18next in the cabinet | Every translation call and message of the new UI would be rewritten; two systems with two message formats would serve one product |

## Consequences

- One more process role in the plane: the Next.js server of the public site (Node.js, own image, stateless, behind the edge). Its outage leaves the cabinet, the API and capture unaffected.
- One more frontend project in the repository and in CI. `site/` follows the frontend rules of CLAUDE.md: feature-first slices, the 200-line limit, the frontend skills and the React doctor gate.
- The cabinet's move from Next.js to Vite is part of F2: routing, `next/link` and `next/navigation`, translations, page metadata and dynamic imports, removal of the sample backend.
- SEO 18.1 is resolved; the rules of 6.2, 6.7, 6.9 and 6.12 bind the public site.

## Revisit when

- The cabinet needs server rendering for a measured reason (for example LCP over 2.5 s on first visit that client rendering cannot fix).
- The public site's server becomes a bottleneck or a cost: move the pages that allow it to static generation.
