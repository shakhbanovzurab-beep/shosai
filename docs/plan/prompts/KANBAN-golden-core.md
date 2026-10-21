# Kanban — the golden core, visual part

Follow the common protocol in `docs/plan/prompts/README.md`. **This package is multi-session**: the first session writes the plan `docs/plan/packages/KANBAN-golden-core.md` and stops for the owner's approval; every later session implements one step of it (session mode in the README).

## Goal

The cabinet's Kanban (`frontend/src/features/kanban/`) gets the **golden core** of a modern task board — the parts nearly every team uses — built in Shosai's own design system, on the cabinet's MSW mocks, ready for `tasks` step 9 to switch it to the real API. The owner decided the scope on 2026-10-21; it is listed below and is not reopened.

Reference for **functionality only**: YouGile (yougile.com), screenshots in `docs/design/references/kanban/`. **Do not copy its look.** The look, spacing, tokens and components are the cabinet's (`frontend/AGENTS.md`, shadcn components in `src/components/ui/`, semantic theme tokens, light and dark themes, existing presets). Where the frontend guide says to follow a screenshot's visual direction, that rule does not apply to these references.

## Scope decided by the owner

**In the golden core:**

1. **Board and columns.** Create, rename, reorder by drag and drop, delete with Undo; a column colour from the theme palette; collapse a column; the card count in the header; the sum of a number field per column (Σ, for example "Estimate in days: 4") when the board has one.
2. **Cards on the board.** Title; cover image (from an attachment); assignee avatar; deadline as a date or a range, overdue shown plainly; priority; the board's visible stickers as compact chips; subtask progress ("2/3" with a bar); comment and attachment counts; recurring-task mark; done cards greyed in a done column. Drag and drop within and between columns, also by keyboard.
3. **Card panel.** Opens over the board without leaving it: title, description (Markdown), stickers, subtasks (add, tick, reorder, Undo), comments thread, attachments through the `files` slice's upload flow, recurrence (daily, weekly on chosen days, monthly), the meeting the task came from with a link.
4. **Stickers — the board's own fields.** System stickers: assignee, deadline, priority, recurrence. Custom stickers created on a board: **a set of states** (each state with a name and a theme colour), **a number**, **a text**. Reuse a sticker from another of the person's boards. Per board, each sticker can be shown on cards or hidden. A settings sheet in the spirit of the first reference screenshot, in Shosai's style. **A new board shows only assignee, deadline and priority**: the board stays quiet until someone needs more.
5. **Filter bar.** One chip per visible sticker, as in the second reference, plus text search; filters combine; the active filter is visible and cleared in one action.
6. **Leo's part, visible.** A field Leo filled (assignee, deadline, priority from a meeting) carries a small mark and the source; the person can change it, and the mark goes. This is the philosophy: Leo organises, the person decides.

**Not in this package** (separate decisions later, do not build or stub them): automations, mirror columns, summary columns, stopwatch, timer and time tracking, sprints, task types beyond custom state sets, card background colours, board backgrounds.

## Read first

- `.claude/CLAUDE.md` in full, especially "Philosophy", "Frontend", "UX principles", "React practices".
- `frontend/AGENTS.md`, `frontend/docs/architecture.md`, `frontend/docs/i18n.md`, `src/i18n/GLOSSARY.md`.
- `docs/plan/slices/tasks.md` — the backend plan. Its §3.2–§3.4 are the contract the mocks must follow; TK-D3, TK-D4, TK-D5, TK-D6, TK-D11 apply to the UI.
- `docs/plan/SLICE_MAP.md` §2.7 and §8.1 (SM-3: one task store).
- The current `frontend/src/features/kanban/` slice in full, and the Notes, Files and Today screens it must stay consistent with.

## Load first

`vercel-react-best-practices`, `vercel-composition-patterns`, `vercel-react-view-transitions`, `web-design-guidelines` (fetch its guidelines and review your screens against them), `shadcn`, and `react-doctor` for the gate.

## Planning session

Write `docs/plan/packages/KANBAN-golden-core.md`:

- **Facts:** what the current kanban slice has, what the tasks plan's contract already covers, what is missing for the golden core.
- **Contract additions.** Every field, resource and call the golden core needs that `docs/plan/slices/tasks.md` does not have yet (subtasks, comments, attachments on a task, recurrence, sticker definitions and values per board, sticker reuse, column sums, column colour and collapse, cover): the shape in the plan's style (`/v1/...`, snake_case, ADR 0008 errors, cursor pages). Add them to the tasks plan as **TK-D12 "golden core", decided by the owner on 2026-10-21**, and say that it revises TK-D7 for labels and colours. Do not touch `backend/`.
- **Screens and states:** board, column menu, card, card panel, sticker settings, filter bar; loading, empty, error, read-only (Jira boards), overflow (TK-D5's 1 000 cards), mobile at 390 px, both themes, RTL (`ar`).
- **Component design:** compound components and composition, no boolean-flag props; data containers separate from presentation; files ≤ 200 lines; no barrels; drag and drop with keyboard support; virtualisation if measurement shows the need.
- **Steps**, each one session, each leaving the cabinet working with its checks: for example 1 — mocks and model for the new contract; 2 — board and columns; 3 — cards; 4 — card panel; 5 — stickers settings; 6 — filter bar; 7 — Leo marks, accessibility and performance pass. Adjust to what the code needs.
- **What the owner must provide:** a design review of the first built screen before the rest follow it.

Stop for approval. No application code in the planning session.

## Implementation sessions

- One step per session; the mocks follow the contract additions exactly, so that `tasks` step 9 only swaps the data source.
- All user-panel text goes through the `use-intl` catalogs in all 16 languages (`npm test` checks them).
- Check visually: run Vite and take screenshots of each new state in both themes at 1440 and 390 px. If Chromium fails with `ERR_NETWORK_CHANGED` on this host, run Vite and the browser inside `unshare -n`.
- Gates from `frontend/`: `npm run typecheck`, `npm test`, `npm run build`, `npm run doctor -- --score` → `100`. Measure: no CLS above 0.1 when cards load or move; INP under 200 ms when dragging a card on a board of 300 cards.
- Clean up after manual checks: stop Vite, revert any local setting you changed.
- Mark the step done in the package plan, update STATUS.md (row `kanban-golden-core`), report with the screenshots' paths and the skills loaded, wait for «Принято».

## Definition of done

Every item of "In the golden core" works on the mocks in the cabinet, in both themes, on desktop and mobile, by mouse and keyboard; the tasks plan carries TK-D12 with the full contract; the frontend gate is 100; the owner has reviewed the screens.
