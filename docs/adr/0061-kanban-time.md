# ADR 0061 — Kanban time: stopwatch, timer and time tracking as system fields

- **Status:** accepted by the owner on 2026-10-22, with the plan of Kanban time.
- **Packages:** `kanban-time` (the cabinet's `kanban` slice on mocks), `tasks` (TK-D12 and §3.8, implemented with the board and task steps).
- **Context documents:** [Kanban time plan](../plan/packages/KANBAN-time.md) §2–§3; [Kanban golden-core plan](../plan/packages/KANBAN-golden-core.md) §1.4; [tasks plan](../plan/slices/tasks.md) §3.8.

## Context

The golden core left the stopwatch, the timer and time tracking for a later decision. On 2026-10-22 the owner asked for the three as YouGile has them: a stopwatch with three board automations, a countdown timer, and plan and fact on a task.

## Decision

1. **The three are system fields** (`stopwatch`, `timer`, `time_tracking`), on every board, off until shown, never on a Jira board; their values belong to the task (ADR 0060 §4).
2. **The stopwatch is the task's own clock**, not a person's working time: one per task, any number running; per-column time with the automation.
3. **Its automations are per board and run on the server** inside the card's creation, move and status change: start when a task appears on the board, restart on a move between columns with the sum per column, stop when done (defaults off, on, on).
4. **The timer counts down a length the person sets** (presets and a custom length), can be paused, resumed, changed and removed, says "Time is up" at zero and keeps counting the overrun; it is not tied to the deadline.
5. **Plan and fact are two durations typed by the person**; a stopped stopwatch offers to add its time to the fact, never automatically.
6. **Time is the server's**: running clocks are start moments, spans are stored per task and column, every reply carries `server_now`; cards move once a minute, the open panel every second, one clock per board.
7. **Nothing proactive**: no notice when a timer runs out and no clock driven by Leo in this package.

## Consequences

- TK-D12 and tasks §3.8 gain the three fields on the task, the stopwatch, timer and plan-and-fact routes, the stopwatch's board automations and a `task_clock_spans` table.
- The cabinet's Fields sheet, cards, panel, column headers and filter bar gain the three fields; durations are worded by `Intl.DurationFormat`.
- Personal time logging (entries per person, timesheets) and timer notices stay out until decided.
