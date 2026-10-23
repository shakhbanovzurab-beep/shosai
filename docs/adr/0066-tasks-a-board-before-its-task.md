# ADR 0066 — A write of tasks takes the reader's board before its task

- **Status:** proposed on 2026-10-23 by the agent building tasks' step 4a, under the owner's instruction of 2026-10-23 to carry the tasks slice through on its own and decide unusual points by industry practice; for the owner's review. Applies §14's rules on concurrency and error handling; changes no contract.
- **Packages:** `features.tasks` (`application/scoping.py` and every write that locks a task).
- **Context documents:** target architecture §9, §14; [tasks plan](../plan/slices/tasks.md) §3.5 flow 3, §3.9, step 4a.

## Context

Two kinds of write touch both a board and a task. A card's move takes the board's row lock first — writes to one board go one after another (§3.5 flow 3) — then the task's. A change of the task itself — in the panel, its checklist, its values, its stopwatch — took the task's row lock first and then updated the reader's board to raise its revision, as the cabinet's mocks do. The two took the same rows in opposite orders. Step 4a's test of a manual stop racing an automated move found it: PostgreSQL detected the deadlock and aborted one side, which the person sees as a 500. A change in the panel racing a move of the same card on the board fails the same way; it was latent since steps 3 and 4.

## Decision

Every write of tasks locks the reader's board where the task sits before it locks the task's row (`scoping.lock_boards_of`, called by `locked_task` whenever it locks, and by the bulk deletion for its tasks' boards, which go in the order of their ids; the tasks there go in the order of theirs). A board's own writes already lock the board first. A write therefore always takes a board, then tasks, and no two writes wait on each other in a circle. The order is a rule of the slice: a new write that locks a task goes through `locked_task`, or takes `lock_boards_of` first.

## Consequences

- The deadlock is gone: the race tests of step 4a — a stop racing a move, a panel change racing a move, six rounds each — pass, and fail without the rule.
- A write of one task takes one statement more, a primary-key lock of one board row; writes of different tasks on one board now go one after another, as moves on it already did. A person's board is written by its person, so the queue is a person's own clicks.
- A task on no board of the reader locks no board; a workspace's task changed by two members takes each one's own board, then the shared task, so they never wait in a circle either.
