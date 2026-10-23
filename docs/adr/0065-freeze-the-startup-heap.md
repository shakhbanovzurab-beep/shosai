# ADR 0065 — Freeze the startup heap for the garbage collector

- **Status:** proposed on 2026-10-23 by the agent building tasks' step 4, under the owner's instruction of 2026-10-22 to carry the tasks slice through on its own and decide unusual points by industry practice; for the owner's review. Applies nfr-7 and §14's performance rule; changes no contract.
- **Packages:** `composition` (every long-running role), `core.runtime`.
- **Context documents:** target architecture nfr-7, §3 (the design point), §16.3; [tasks plan](../plan/slices/tasks.md) §3.14, step 4.

## Context

A board read of 1 200 cards answered in about 170 ms, yet its p95 was 743 ms: every ninth request or so paused for 600–800 ms. With the cyclic garbage collector switched off the pauses vanished. A Shosai process imports every slice and builds its apps before it serves — about 375 000 objects that live as long as the process. Measured on that heap, one full pass of CPython 3.14's cyclic collector takes 288 ms, and it walks those objects on every pass, pausing whatever request runs then. Large responses allocate enough to trigger such passes regularly, so every role's tail latency carried the cost of its own startup.

## Decision

Once a long-running process has started its role, it collects the startup garbage and freezes what lives on (`gc.collect()`, then `gc.freeze()`, in `core/runtime/heap.py`, called by `composition/process.py` before readiness turns ready). Later passes walk only what the work itself allocates; the frozen objects are never collected, which is right for objects that live as long as the process. The process logs how many objects it froze.

## Consequences

- Measured: a full pass on the imported heap drops from 288 ms to under 1 ms. The 1 200-card board read's p95 fell from 743 ms to 130 ms (median 94 ms) together with the read's own changes of step 4; without the freeze its pauses alone kept p95 above 600 ms.
- Every role gains, API, WS, workers and scheduler alike; there is nothing to configure.
- Memory freed only by a cycle that started before the freeze stays held for the process's life: startup garbage is collected first, so only long-lived objects are frozen.
- A latency test models a running process by freezing its heap before it measures, as `tests/features/tasks/test_board_latency.py` does.
