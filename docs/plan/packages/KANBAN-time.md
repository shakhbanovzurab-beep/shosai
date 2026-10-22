# Kanban time — package plan

The request: the owner's message of 2026-10-22 in the Kanban session — "add this functionality" with YouGile's three system fields: **Timer** («Таймер»: a countdown showing how much time is left until the task's planned completion), **Time tracking** («Таймтрекинг»: plan and fact on the board's tasks) and **Stopwatch** («Секундомер», with board automations: start when a task appears on the board; restart when it moves between columns and show the sum per column; stop when it is done). It reverses the "Out" line of [KANBAN-golden-core §1.4](KANBAN-golden-core.md), which left the three for a later decision. Contract: [tasks plan](../slices/tasks.md) TK-D12 and §3.8, extended here. Cabinet slice: `frontend/src/features/kanban/`.

- **Status:** written on 2026-10-22 and **approved by the owner the same day**: KT-D1…KT-D8 as proposed, KT-D3 confirmed in the owner's words (a length the person sets — 30 min, 1 h, 4 h, 1 day, a week or their own — with pause, change, "Time is up" and the overrun; not tied to the deadline); recorded in [ADR 0061](../../adr/0061-kanban-time.md).
- **Who decided what.** The scope (the three fields and the stopwatch's three automations) and the decisions of §2 are **the owner's, of 2026-10-22** (proposed by this plan, approved as written). The contract, screens and steps are this plan's design, derived from them.
- **Dependencies:** the golden core's contract, mocks and screens (done). Like the golden core, the package works on MSW mocks of `/v1`; `tasks` step 9 switches the screens to the API, and the backend implements the contract additions of §3 with TK-D12.
- **Philosophy check:** time is shown, not demanded. The three fields are off on a new board; a card shows a clock only while it runs or when time is up; nothing beeps or nags here (reminders are proactive's, tasks plan §6). The stopwatch counts by itself once the board says so — the person doesn't press start on every card.

---

## 1. Facts this plan rests on

- **The field model fits.** System fields (`assignee`, `due`, `priority`, `recurrence`) are on every board, shown or hidden there; values belong to the task (KG-D4). The three new ones join them as system fields: on every board, off by default, shown with the "Show on cards" switch in the Fields sheet.
- **A deadline is a calendar day.** Time of day on a task is out of the tasks plan (§6). The timer is the only part of a task that counts in hours and minutes toward an end, so it does not replace the deadline.
- **Jira boards show Jira's fields only** (KG-D8): the three are not offered there.
- **Clocks must not trust the browser.** A person opens the board on two devices and in a workspace with others; a running clock is a start moment on the server, and every screen derives what it shows from it.

## 2. Decisions

| # | Question | Proposal | What follows |
|---|---|---|---|
| **KT-D1** | What does the stopwatch measure? | **The task's own clock, not a person's working time**: how long the task has been in work, and, with the per-column automation, how long it spent in each column. One per task; any number run at once (a board full of tasks in progress all count). Start, stop and reset from the panel; reset asks first | It is a cycle-time meter like YouGile's. Personal time logging with who and when is not this package (it would be a timesheet: entries per person, reports) |
| **KT-D2** | The stopwatch's automations | **Exactly the three of the request, per board, in the field's "Set up" dialog**: start when a task appears on the board (created there or moved in from elsewhere); restart when it moves to another column and show the sum per column (the column header gets "⏱ 3 d 4 h"); stop when the task is done (moved to a done column or marked done). Defaults on a board that turns the stopwatch on: off, on, on — as in the reference | The server applies them in the same transaction as the move, the creation or the status change, so no screen has to remember to |
| **KT-D3** | What is the timer counting to? | **Confirmed by the owner. A length of time the person sets** ("2 hours", "3 days"; presets 30 min, 1 h, 4 h, 1 d, 1 week and a custom length): it starts counting down at once; it can be paused and resumed, changed or removed. At zero the card says "Time is up" and keeps counting the overrun. Not tied to the deadline | A timer to a moment ("until 18:00") would need time of day on a task, which the tasks plan leaves out. If the owner wants it to count to the deadline's end instead, the timer becomes automatic and needs no input |
| **KT-D4** | Plan and fact in time tracking | **Two durations on the task, both typed by the person** (hours and minutes; "1h 30m", "1,5 h" and "90 min" all read): plan is the estimate, fact what was spent. A stopwatch that stops offers "Add 45 min to the fact" in its toast — one click, never automatic. The card shows "2h 30m / 4h" and turns the fact red when it passes the plan; the column shows Σ plan and Σ fact | Fact as typed numbers keeps it simple and honest; per-person time entries are the timesheet KT-D1 leaves out |
| **KT-D5** | Whose are the values? | **The task's, like every field value (KG-D4)**: everyone who sees the task sees and may change them; on a workspace task, as anything else on it. The board's owner turns the fields on and sets the stopwatch's automations | Nothing new in access: the task's own rules apply |
| **KT-D6** | How often does a card's clock move? | **Once a minute on cards ("2 h 15 min"), every second in the open panel**; one clock per board drives every running card, so 300 cards with running stopwatches cost one timer, not 300. Durations are worded by `Intl.DurationFormat` in the person's language | Seconds on a board of cards would be noise and work; the panel is where a person watches a single task |
| **KT-D7** | Filters for the three | **A chip each, like every visible field**: stopwatch — Running, Stopped, Not started; timer — Running, Time is up, No timer; time tracking — Over plan, Within plan, No plan | Keeps "a chip per visible field" (§4.5 of the golden core) true |
| **KT-D8** | Leo and notices | **Nothing proactive in this package**: no notice when a timer runs out, Leo doesn't start or stop clocks. Both are later decisions (proactive; Leo's errands), and the values are in the task for Leo to read | The quiet board stays quiet |

## 3. Contract additions (to TK-D12, tasks §3.8)

- **System field ids** gain `stopwatch`, `timer`, `time_tracking` (off on every board until shown; never on a Jira board — `jira_unsupported`).
- **Task** (and `Card`) gains, each `null` while unused:
  - `stopwatch: {running_since: datetime | null, total_ms: int, by_column: {column_id: ms}}` — `total_ms` and `by_column` count closed spans; a running one adds `now − running_since` on screen.
  - `timer: {length_ms: int, ends_at: datetime | null, paused_left_ms: int | null}` — running when `ends_at` is set, paused when `paused_left_ms` is.
  - `time_tracking: {plan_minutes: int | null, fact_minutes: int | null}`.
  - The reply carries `server_now` (the moment the server answered), so a screen corrects its own clock once per read.
- **Routes:** `POST /v1/tasks/{id}/stopwatch/start`, `…/stop`, `…/reset`; `PUT /v1/tasks/{id}/timer {length_ms}`, `POST …/timer/pause`, `…/resume`, `DELETE …/timer`; plan and fact through `PATCH /v1/tasks/{id}` (`plan_minutes`, `fact_minutes`, `null` clears). Each answers the task's three fields; repeating a start or a stop changes nothing (idempotent by state).
- **Automations:** `PATCH /v1/boards/{id}/stickers/stopwatch {visible?, automations?: {start_on_arrival, restart_on_move, stop_on_done}}`; `BoardSticker` of the stopwatch carries `automations`. Applied by the server inside the card's creation, move and status change.
- **Data:** a `task_clock_spans` table (task, kind `stopwatch`, column, started_at, stopped_at) under the task's home, plus the timer and the two durations on the task row. Spans keep per-column sums exact after any number of moves.

## 4. Screens

- **Fields sheet:** the three as system fields with the "?" explanation (the reference's words, in the person's language) and "Show on cards"; the stopwatch's card adds "Set up" (the three automations as checkboxes, "Automations: 2" on the card).
- **Card:** a stopwatch chip while it runs ("⏱ 2 h 15 min"), a timer chip while set ("⏳ 1 h 5 min left", red "Time is up · +20 min"), a tracking chip when plan or fact is set ("2h 30m / 4h", fact red over plan). Hidden fields show nothing.
- **Panel:** rows like the other fields — stopwatch (time, Start / Stop, Reset with a confirmation, per-column times when the automation is on), timer (length presets and custom, Pause / Resume, Change, Remove), time tracking (plan and fact inputs).
- **Column header:** Σ stopwatch per column (with the automation), Σ plan and Σ fact of the cards it shows.
- **Filter bar:** the chips of KT-D7.
- **States:** every action optimistic with its own rollback (the panel's `changeTask`); a clock that the server corrected jumps without animation; reduced motion changes nothing here (no motion).

## 5. Steps

Every step loads the frontend skills (as the golden core), ends with typecheck, test, build and doctor 100, scripted browser checks, the Arabic RTL smoke, screenshots at 1440 and 390 in both themes, and this table and STATUS updated.

| Step | Content | Done when |
|---|---|---|
| 1 | **Contract and mocks.** §3 written into tasks §3.8 and `frontend/docs/kanban-api.md`; types; mock store with spans, the timer, plan and fact, the three automations applied on creation, move and done; seed values on the Work board | Unit tests: per-column sums after moves, start on arrival, stop on done, a timer paused and resumed, idempotent start and stop, Jira refused. **Done 2026-10-22:** contract in tasks §3.9 and `kanban-api.md`; `domain/time-contract.ts`; the mock store's `clock-ops` (spans per column, timer, plan and fact, automations hooked into creation, landing, the next recurring task, moves and done) and `clock-routes`; the Work board seeded with a running stopwatch, a timer running and one past zero, plan and fact; the three fields in the Fields sheet (names and icons, no chips or filters yet) in 16 languages and the glossary; 8 tests (also: never on a Jira board), a Fields sheet check in the browser at 1440 and 390, both themes, Arabic |
| 2 | **Fields and cards.** The three in the Fields sheet with explanations, the stopwatch's "Set up"; card chips; one minute clock per board; durations in 16 languages | Hiding a field removes its chips; 300 running cards keep one timer (measured) |
| 3 | **Panel, columns, filters.** Panel rows with every action, the "add to fact" offer after a stop, column sums, filter chips | Every action works by mouse and keyboard, in Arabic too; a filtered link reproduces the view |
| 4 | **Pass.** Guidelines review, RTL, the large boards re-measured with running clocks | INP and CLS targets of the golden core hold |

## 6. Risks

- **Clock drift between devices:** handled by `server_now` per read; a person who changes the device clock sees a corrected time on the next read.
- **Automations racing a manual stop:** the server applies both in order inside the task's row lock; the screen shows what the server answered.
