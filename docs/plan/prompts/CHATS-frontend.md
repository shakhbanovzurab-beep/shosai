# Chats — the visual part, frontend first

Follow the common protocol in `docs/plan/prompts/README.md`. **This package is multi-session**: the first session writes the contract and the package plan and stops for the owner's approval; every later session implements one step (session mode in the README). The backend slice `chats` comes after this package and implements exactly the contract written here.

## Goal

A team connects the chats it already uses to a Shosai workspace, and Leo turns what was said there into tasks and digests **on request**. The cabinet gets every screen for this, built in Shosai's design system on MSW mocks of the slice's `/v1` contract. Decided by the owner on 2026-10-22: [ADR 0062](../../adr/0062-team-chats-through-leo-on-demand.md), [SLICE_MAP](../SLICE_MAP.md) §4.2 card 27. Shosai gets **no messenger of its own**: no channels, feed, voice notes, polls or reactions — do not design them.

## Scope decided by the owner

1. **Connect a chat** — in the workspace's settings, a "Team chats" section (the workspace slice's settings screens in `frontend/src/features/workspace/`). Only messengers that work are offered; at launch Telegram and Slack (priority 1 of the card's list). Nothing inert, no "coming soon" rows.
   - **Telegram:** add Shosai's bot to the group, send the one-time connect code the screen shows, choose what the chat is bound to (the whole workspace or one project), choose the mode — **"Only messages to Leo"** (privacy mode on) or **"Every message, for digests"** (privacy mode off, with the instruction to change it) — and accept the data notice: Shosai stores the messages of this chat in the workspace's region for the retention period, including those of people who are not Shosai users. The screen says that Telegram gives Shosai only messages written after the bot joined.
   - **Slack:** connect the workspace's Slack app (the OAuth handoff is mocked), pick channels, bind each to the workspace or a project.
2. **The chats list** — messenger, chat name, binding, mode, last activity, state (working, needs attention: bot removed, rights missing, token expired — each with the one action that fixes it); change binding or mode; disconnect with confirmation that names what is erased.
3. **Link my messenger account** — in the person's account settings: link Telegram (a deep link to the bot with a one-time token; the confirmation state when it comes back), show linked accounts, unlink. Slack members are matched by their verified email where it equals the Shosai account's — propose in the plan whether that needs a confirmation. A quiet hint in the workspace for a member who is not linked: why linking matters ("ask Leo from the chat") — once, dismissible.
4. **Leo's digest** — the result of "go through #release for the week" rendered in Leo's conversation (the `leo` feature): decisions, open questions, promises (who, what, when), each with a link to the message and a "Make a task" action that goes through Leo's approval card; an empty digest and "the chat has no messages before the bot joined" states.
5. **The source on a task** — a task created from a chat shows "From Telegram · <chat>" with a link to the message, on the card face and in the card panel (the `kanban` feature; the golden core's source line); the field it needs is added to the tasks contract.
6. **What Leo answers in the chat** is text in the messenger, not a cabinet screen: write its templates (task created, need clarification, not linked, not a member, no rights) in the plan as English model-facing text with the language rule of CLAUDE.md, so the backend uses them as they are.

## Read first

- `.claude/CLAUDE.md` in full, especially "Philosophy", "Frontend", "UX principles", "Prompts and model-facing text".
- ADR 0062, ADR 0039 (one account, Leo sees what the person may access), ADR 0029 (Leo's tools live in the slice owning the data), `docs/design/leo/ARCHITECTURE.md` (the Action Gateway and approvals).
- `docs/plan/SLICE_MAP.md` card 27 and the cards of `identity`, `workspaces`, `connectors`, `agent`, `tasks`.
- `frontend/AGENTS.md`, `frontend/docs/architecture.md`, `frontend/docs/i18n.md`, `src/i18n/GLOSSARY.md`; the current `workspace`, `settings`, `leo` and `kanban` features.
- Each messenger's own developer documentation for what the screens promise (Telegram Bot API: groups, privacy mode, deep linking; Slack: OAuth, Events API, permalinks). Do not rely on blogs or forums.

## Load first

`vercel-react-best-practices`, `vercel-composition-patterns`, `vercel-react-view-transitions`, `web-design-guidelines` (fetch its guidelines), `shadcn`, `agent-architecture` (Leo's digest and approvals), and `react-doctor` for the gate.

## Planning session

1. **The contract**, written as the first section of `docs/plan/slices/chats.md` — "Contract (decided with the frontend, 2026-10-22)": every resource and call the screens need (`/v1/workspaces/{id}/chats*`, the connect code, the Slack handoff, `/v1/me/messenger-links*`, the digest's result shape as Leo's tool result, the task's `chat` source), in the style of the tasks plan §3.8: `/v1/...`, snake_case, ADR 0008 errors, cursor pages. Mark it as the owner's scope with the contract proposed by you, awaiting approval. The rest of `chats.md` (data, flows, steps) is written later by the backend slice's planning session. Add the task's `chat` source to `docs/plan/slices/tasks.md` as **TK-D13**, and the messenger link to `docs/plan/slices/identity.md` as a requirement for a later step.
2. **The package plan** `docs/plan/packages/CHATS-frontend.md`: facts, decisions you need from the owner (each with a proposal and its trade-off), screens and states (loading, empty, error, needs attention, read-only for non-admins, mobile at 390 px, both themes, RTL), component design (composition, no boolean-flag props, files ≤ 200 lines, no barrels), and **steps**, one session each — for example: 1 contract and mocks; 2 team chats section and the Telegram connect flow; 3 Slack connect and the chats list; 4 messenger link in account settings; 5 Leo's digest card and the task's source; 6 accessibility, RTL and performance pass.
3. Stop for approval. No application code in the planning session.

## Implementation sessions

- One step per session; the mocks answer exactly the contract, so the backend slice only replaces the data source.
- All user-panel text goes through the `use-intl` catalogs in all 16 languages.
- Check visually in both themes at 1440 and 390 px; if Chromium fails with `ERR_NETWORK_CHANGED` here, run Vite and the browser inside `unshare -n`.
- Gates from `frontend/`: `npm run typecheck`, `npm test`, `npm run build`, `npm run doctor -- --score` → `100`.
- Clean up after manual checks. Commit only your own paths, listed explicitly; other sessions work in the same tree.
- Mark the step done in the package plan and in STATUS.md (row `chats-frontend`), report with screenshot paths and the skills loaded, wait for «Принято».

## After this package

The backend slice `chats` is planned and built with `docs/plan/prompts/S-feature-slice.md`: its planning session keeps the contract of `chats.md` as fixed (a change needs the owner) and adds data, flows, the bot and webhook handling, Leo's tools and steps.

## Definition of done

Every item of the scope works on the mocks in both themes, on desktop and mobile, by mouse and keyboard; `chats.md` holds the approved contract, `tasks.md` TK-D13, `identity.md` the messenger-link requirement; the frontend gate is 100; the owner has reviewed the screens.
