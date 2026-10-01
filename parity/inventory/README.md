# Route and state inventory of the draft

Every route of the draft frontend and every UI state that renders visibly different, as of draft commit `589917e847f7d7213b3af5a3959bcc88c7500fe7` (read on 2026-10-01). This is the source for the parity harness: each state becomes a state definition with fixtures, a marker and a matrix scope.

The routes were taken from the feature manifests (`src/features/*/feature.ts(x)`) and the composition root (`src/app/router/appManifest.ts`). All 55 declared paths are listed below; each is covered in one of the group documents.

| Document | Features | Routes | State rows |
|---|---|---|---|
| [shell-auth-account-billing.md](shell-auth-account-billing.md) | app shell, boot, auth, account, billing, onboarding, referral, downloads, hotkeys | 10 + shell surfaces | 136 |
| [meetings-calendar-knowledge.md](meetings-calendar-knowledge.md) | meetings, calendar, context, knowledge, search | 12 | 185 |
| [leo-prompts-models-mcp-hub.md](leo-prompts-models-mcp-hub.md) | leo, prompts, models, mcp, hub | 9 + Leo widget | 143 |
| [rooms-streams-storage-tracker.md](rooms-streams-storage-tracker.md) | rooms, streams, storage, tracker | 9 | 131 |
| [admin-analytics-support.md](admin-analytics-support.md) | platform-admin, product-analytics, analytics, satisfaction, support, and the admin routes of downloads, models, referral, rooms | 19 | 159 |

A row can name several related states (`a` / `b` / `c`, `step-N` for N = 1…24). Expanded, the inventory holds about 850 states.

## How to read a state

- **State id**: `<feature>.<screen>.<state>`, kebab-case. The id is stable; the harness, the fixtures and the baseline file names use it.
- **How to reach**: URL under `/app`, the data condition (which response the fixtures return), and the interaction.
- **Marker**: a selector or a text that exists only in that state. A screenshot without its marker is rejected: a broken or wrong screen gives a "clean" diff when both sides are equally wrong.
- **Endpoints**: what the page calls, with the TypeScript type in the draft that fixes the response shape.

Markers and interactions prefer roles, `aria-label`, visible text and `data-onboarding` anchors. Draft class names (`.stor-tile`, `.mtg-dock-pill`) are a last resort: v2 is a rewrite and does not have to keep them.

## Routes

Access levels: `public` (anyone), `auth` (signed in), `user` (signed in, not admin), `admin`. "Outside" means the route renders without the app shell.

| Path | Access | Shell | Feature | Document |
|---|---|---|---|---|
| `/` | auth | inside | app | redirect: user → `/analytics`, admin → `/dashboard` |
| `*` | public | outside | app | shell-auth-account-billing |
| `/login` | public | outside | auth | shell-auth-account-billing |
| `/register` | public | outside | auth | shell-auth-account-billing |
| `/reset-password` | public | outside | auth | shell-auth-account-billing |
| `/connect` | public | outside | auth | shell-auth-account-billing |
| `/cabinet/:tab?` | user | inside, also a modal route | account, billing | shell-auth-account-billing; Leo and MCP tabs in leo-prompts-models-mcp-hub |
| `/referral` | auth | inside | referral | shell-auth-account-billing |
| `/download` | auth | inside | downloads | shell-auth-account-billing |
| `/hotkeys` | auth | inside | hotkeys | shell-auth-account-billing |
| `/analytics` | auth | inside | analytics | admin-analytics-support |
| `/meetings` | auth | inside | meetings | meetings-calendar-knowledge |
| `/meetings/:id` | auth | inside | meetings | meetings-calendar-knowledge |
| `/meetings/live` | auth | inside | meetings | redirect → `/meetings` |
| `/import` | auth | inside | meetings | redirect → `/meetings` |
| `/templates` | auth | inside | meetings | meetings-calendar-knowledge |
| `/settings/integrations` | auth | inside | meetings | meetings-calendar-knowledge |
| `/r/:token` | public | outside | meetings | meetings-calendar-knowledge |
| `/calendar` | auth | inside | calendar | meetings-calendar-knowledge |
| `/rooms` | auth | inside | calendar | redirect → `/calendar` |
| `/context` | auth | inside | context | meetings-calendar-knowledge |
| `/knowledge-base` | auth | inside | knowledge | meetings-calendar-knowledge |
| `/prompts` | auth | inside | prompts | leo-prompts-models-mcp-hub |
| `/prompts/:id` | auth | inside | prompts | leo-prompts-models-mcp-hub |
| `/models` | auth | inside | models | leo-prompts-models-mcp-hub |
| `/connect/mcp` | auth | outside | mcp | leo-prompts-models-mcp-hub |
| `/settings/mcp` | auth | inside | mcp | redirect → `/cabinet/mcp`, keeps the query string |
| `/hub` | auth | inside | hub | leo-prompts-models-mcp-hub |
| `/hub/:hubId` | auth | inside | hub | leo-prompts-models-mcp-hub |
| `/rooms/:id` | public | outside | rooms | rooms-streams-storage-tracker |
| `/rooms/join/:invite` | public | outside | rooms | rooms-streams-storage-tracker |
| `/live/:token` | public | outside | streams | rooms-streams-storage-tracker |
| `/studio/:id` | public | outside | streams | rooms-streams-storage-tracker |
| `/storage` | auth | inside | storage | rooms-streams-storage-tracker |
| `/s/:token` | public | outside | storage | rooms-streams-storage-tracker |
| `/tracker` | auth | inside | tracker | rooms-streams-storage-tracker |
| `/tracker/:projectId` | auth | inside | tracker | rooms-streams-storage-tracker |
| `/support` | auth | inside | support | admin-analytics-support |
| `/dashboard` | admin | inside | platform-admin | admin-analytics-support |
| `/costs` | admin | inside | platform-admin | admin-analytics-support |
| `/admin/users` | admin | inside | platform-admin | admin-analytics-support |
| `/admin/tariffs` | admin | inside | platform-admin | admin-analytics-support |
| `/admin/finance` | admin | inside | platform-admin | admin-analytics-support |
| `/admin/security` | admin | inside | platform-admin | admin-analytics-support |
| `/admin/monitoring` | auth | inside | platform-admin | redirect → `/admin/security` |
| `/admin/abuse` | auth | inside | platform-admin | redirect → `/admin/security?tab=queue` |
| `/admin/client-errors` | admin | inside | platform-admin | admin-analytics-support |
| `/admin/prompts` | admin | inside | platform-admin | admin-analytics-support |
| `/admin/analytics` | admin | inside | product-analytics | admin-analytics-support |
| `/admin/satisfaction` | admin | inside | satisfaction | admin-analytics-support |
| `/admin/support` | admin | inside | support | admin-analytics-support |
| `/admin/app` | admin | inside | downloads | admin-analytics-support |
| `/admin/ai-models` | admin | inside | models | admin-analytics-support, leo-prompts-models-mcp-hub |
| `/admin/affiliates` | admin | inside | referral | admin-analytics-support |
| `/admin/livekit` | admin | inside | rooms | admin-analytics-support, rooms-streams-storage-tracker |

Surfaces without a route of their own, inventoried on a host route: the boot gate, the app shell (sidebar, top bar, ticker), the command palette, the connection overlay, toasts, the upload panel, the onboarding tour and checklist, the Leo chat widget, the satisfaction card and the paywall.

`*` does not render a page in the SPA: it replaces the location with the landing's `/404/` (`/<lang>/404/` for other languages). The parity harness records the redirect target, not a screenshot.

## What the harness cannot replay

LiveKit rooms and stream stages need a live SFU and WebRTC media. The harness replays HTTP, server-sent events and WebSocket frames, not media. States that only exist with a connected SFU (participant tiles, live whiteboard sync, stage video) are listed in [rooms-streams-storage-tracker.md](rooms-streams-storage-tracker.md) but are outside the screenshot matrix. Everything those pages render over HTTP alone — lobby, connecting, error, ended, panels, menus, dialogs — is in the matrix.

## Draft defects recorded as states

The draft has states that look broken. They are inventoried as they are, because parity means the same screen; whether v2 keeps or fixes each one is decided by the slice with the user. The list is at the end of each group document ("Findings", "Bugs", "Cross-cutting notes"). Examples: payment-return toasts showing raw keys (`cab.paySuccess`), endless spinners instead of error UI on `/referral`, `/hotkeys`, `/models` and most admin pages, the hotkeys page crashing on an incomplete map.
