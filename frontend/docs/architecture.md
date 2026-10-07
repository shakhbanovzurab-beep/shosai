# Frontend architecture

Feature-first, organised as vertical slices, with Clean Architecture layers inside each slice.
`npm run lint:architecture` checks the rules below.

## Top level

```
src/
  app/          Routing only: pages, layouts, route handlers, metadata. Thin adapters over features.
  features/     Vertical slices, one per business capability (see the catalogue below).
  components/   Shared UI with no business knowledge: ui/ (shadcn), calendar/ (vendored), feedback, menus…
  hooks/        Shared generic React hooks.
  lib/          Shared business-agnostic code: HTTP client, polling resource, i18n, formatting primitives.
  i18n/         Interface languages: next-intl request config, message catalogs, glossary (docs/i18n.md).
  server/       Shared server infrastructure: forwarding to the FastAPI backend.
  config/       App-wide configuration.
  styles/       Theme presets and vendored stylesheets.
  scripts/      Tooling (theme preset generator, architecture check).
```

Code goes into the shared layer only when it is generic (knows nothing about a business capability)
and is used by more than one slice. Everything else belongs to a slice. Shared code never imports
from `features/` or `app/`.

## A slice

```
features/<slice>/
  index.ts      Public client-safe API: what pages and other slices may use.
  server.ts     Public server API: route handlers and server-only reads.
  domain/       The business core: API contract types, rules, validation schemas, pure formatting.
  data/         Static demo fixtures for screens that have no backend yet.
  api/          Browser gateway: typed calls to the slice's own /api routes.
  model/        Client application layer: stores, resources, use-case actions, hooks.
  ui/           React components.
  server/       Server side: route handlers, in-memory demo repositories, backend forwarding.
```

A slice has only the folders it needs. Files inside a slice import each other with relative paths.

### Dependency rule

Dependencies point inward. Each layer may import only these layers of its own slice:

| Layer    | May import                         | Must not depend on                                        |
| -------- | ---------------------------------- | --------------------------------------------------------- |
| `domain` | `domain`                           | React, Next.js, stores, toasts, icons, UI, HTTP, browser APIs, other slices |
| `data`   | `domain`, `data`                   | same as `domain`                                          |
| `api`    | `domain`, `api`                    | React, Next.js, stores, UI (HTTP primitives such as `fetch`, `XMLHttpRequest` and `@/lib/api-client` are its job) |
| `model`  | `domain`, `data`, `api`, `model`   | `ui`, `server`, UI components                             |
| `ui`     | `domain`, `data`, `model`, `ui`    | `api` (go through `model`), `server`                      |
| `server` | `domain`, `data`, `server`         | client layers                                             |

- **Business logic lives in `domain/`** and is plain TypeScript: it can be unit-tested and reused by
  the route handlers and the UI alike. Zod schemas and `Intl` formatting are allowed there.
- **Use cases live in `model/`**: an action calls the gateway, updates the store, rolls back on
  failure and reports through a toast. Components call actions; they never call `api/` directly.
- **Server Actions** (`"use server"` modules in `server/`) are RPC endpoints: `model/` and `ui/` of the
  same slice may import them.
- **Route handlers live in the slice** (`server/`), grouped per route as objects keyed by HTTP
  method. Each first forwards to the FastAPI backend when `BACKEND_API_URL` is set and otherwise
  answers from the slice's in-memory demo.

### Public API and cross-slice contracts

- Anything outside a slice imports only `@/features/<slice>` (`index.ts`) or
  `@/features/<slice>/server` (`server.ts`). Deep imports are violations.
- `index.ts` exports only what is used elsewhere and never re-exports server code.
  `server.ts` is imported only by route files and by other slices' server code.
- Client layers of a slice use other slices' `index.ts`; server code uses other slices' `server.ts`.
  `domain/`, `data/` and `api/` never depend on other slices.
- Slices depend on each other in one direction only; the check rejects cycles.
- `package.json` declares `"sideEffects": ["*.css"]`, so bundlers drop the modules a public API
  re-exports but a consumer doesn't use. Keep module scope free of side effects that must run on
  import alone; a module is only kept when something it exports is used.
- User-panel text comes from the message catalogs (`useTranslations` / `getTranslations`, see
  `docs/i18n.md`), in the request's language: the user's choice in `/app`, always Russian in `/admin`.
  The admin panel's own screens are written in Russian directly.

## Routing layer

Route files compose features and own only routing concerns: metadata, `searchParams` parsing and
segment config. Redirects for old or moved URLs live in `next.config.mjs`, not in pages.

```tsx
// src/app/(main)/admin/plans/page.tsx
import { PlansScreen } from "@/features/admin-plans";

export const metadata: Metadata = { title: "Тарифы и промокоды" };

export default function Page() {
  return <PlansScreen />;
}
```

```ts
// src/app/api/admin/plans/route.ts
import { plansRoute } from "@/features/admin-plans/server";

export const dynamic = "force-dynamic";
export const { GET, POST } = plansRoute;
```

## Slice catalogue

| Slice                    | Owns                                                                 |
| ------------------------ | -------------------------------------------------------------------- |
| `shell`                  | Panel layout, sidebar, header, navigation, page search               |
| `preferences`            | Theme and layout preferences, fonts, the pre-hydration boot script   |
| `leo`                    | The Leo assistant widget and its streaming `/api/leo` endpoint        |
| `settings`               | The user's settings dialog, account, billing, data, connectors (OAuth) |
| `productivity`           | The user panel home with the contribution skyline                    |
| `mail`                   | The inbox (`/app/inbox`), its preview page, and Leo's triage, summaries and reply drafts there (`/api/mail/insights`) |
| `calendar`, `kanban`, `notes` | User panel workspace tools                                      |
| `file-manager`           | The account's files, the one place they are stored (`/api/files`), which ones Leo uses, sharing and transferring them to workspaces |
| `studio`                 | Context, prompts, skills and models; the shared model catalogue      |
| `knowledge-base`         | Knowledge: what Leo answers from in Personal (a view over File Manager), the index settings and connected sources |
| `support`                | The user's support tickets                                           |
| `hub`                    | Hubs (`/app/hub`): what each piece of work has unresolved, its topics' history, digests, the brief, meeting prep, a meeting's hub, Leo's hub context. See `hub-api.md` |
| `workspace`              | Workspaces (`/app/w/{slug}/*`): members, teams, projects, roles, shared meetings, decisions, tasks, knowledge, settings; the Personal/Workspace switcher the `shell` sidebar shows; and the bridges that show workspace work in Personal (`/api/me/*`) |
| `admin-*`                | Back-office screens, one slice per `/admin/<screen>` route           |

### Personal and workspaces

One account works in Personal (its own tools) and in any number of workspaces. Objects are never
copied between them; see `workspace-api.md` for the model. The links between slices:

- `workspace` reads recordings from `notes` (client-safe `@/features/notes` for types, `server` for the
  demo recordings). `notes` doesn't know about workspaces: the route `notes/[id]/page.tsx` composes
  the note with the workspace's share button and its live tasks, passed in through `NoteDetail` props.
- `meetings`, `productivity`, `file-manager` and `knowledge-base` render small bridges exported from
  `@/features/workspace` (meetings shared with you, your workspace tasks, sharing a file, what your
  workspaces let Leo use).
- `workspace` doesn't know about File Manager either. Its "Share from my files" dialog takes the
  list of files as a `picker` slot, which the workspace routes fill with File Manager's
  `WorkspaceFilePicker`; the picker reads the selection through the exported `useFileSelection`.
  On the server, File Manager tells the workspace when a file is deleted (`withdrawFile`) or
  transferred (`adoptFile`).
- `knowledge-base` reads the account's files from `@/features/file-manager` (one resource for both
  screens), so a file is never listed from two stores.
- `kanban`, `leo` and `upgrade` read the account's workspace data on the server through
  `@/features/workspace/server`: tasks projected onto a board, the knowledge Leo may use, the seat.
  `leo` also reads the files Leo may use from `@/features/file-manager/server`, and `file-manager`
  and `knowledge-base` read the plan's limit from `@/features/upgrade/server`.
- `admin-workspaces` (Admin › Пространства) reads and controls every workspace through
  `@/features/workspace/server` (`platformWorkspaces`, `setSeats`, `suspendWorkspace`, …) and shows
  metadata and counts only, never what the workspace contains.
- `shell` picks the sidebar from the URL (`/app/w/{slug}` is a workspace, the rest is Personal) and
  gives Leo the current context.

Placeholder pages (Meetings, Upgrade, Download) are composed from `@/components/page-placeholder`
and need no slice.

## Known exception

`src/lib/preferences/theme.ts` holds the theme preset list for the `preferences` slice but stays in
`src/lib/`: `npm run generate:presets` writes it and the pre-commit hook stages it at that path. Move it
into `src/features/preferences/domain/` together with updating `src/scripts/generate-theme-presets.ts`
and `.husky/pre-commit`.

Message catalogs are owned by slices (one namespace per slice) but live together in
`src/i18n/messages/<language>/<namespace>.json`: the loader that reads them for every request is shared
code, which may not import features.

## Adding a feature

1. Create `src/features/<slice>/` with the layers it needs, starting from `domain/` types.
2. Export the screen from `index.ts`; add `server.ts` when it has route handlers.
3. Add the thin route files under `src/app/`, and the navigation entry in the `shell` slice.
4. Run `npm run lint:architecture`.
