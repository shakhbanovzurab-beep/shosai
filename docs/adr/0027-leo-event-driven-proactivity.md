# ADR 0027 — Proactivity from events, trigger rows and state transitions, judged per candidate

- **Status:** accepted by the owner on 2026-10-08. **Extended** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §12 (time triggers as rows run by the scheduler).
- **Packages:** S09 (`proactive`), S11; event producers S04, S07, S12, S13, S16.
- **Context documents:** [Leo architecture](../design/leo/ARCHITECTURE.md) §9; [Leo audit](../design/leo/AUDIT.md) P1–P8, A5; ARCHITECTURE.md §8.1 (events, errands), §12.

## Context

The draft's proactive slice has a sound core:

- one choke point (`offer`);
- pure, explainable restraint rules with verdict codes;
- defaults toward silence;
- the insistence ladder `initiative / requested / explicit`;
- a durable delivery state machine with replay on `hello`.

Around that core, the audit found:

- **P1:** urgency is a constant per kind; the user's attention is unknown.
- **P2:** feedback has no UI; acks mean "the frame arrived".
- **P3:** the sources are global scans over all users every 5 minutes with unordered `LIMIT 500`. No domain event is consumed, although the outbox exists.
- **P5:** a background tab swallows every nudge, and non-durable nudges are lost.
- **P6:** three reminder systems and three schedulers.
- **P7:** mail summaries are generated before the gates.
- **A5:** untrusted mail text is written into the thread as an assistant turn.

## Decision

1. **Signals, not scans.** Inputs are:
   - outbox subscriptions to domain events: meetings notes ready or ended, mail received, calendar and task changes, commitment due, connector broken, hub topic looped, errand failed;
   - **time triggers** as rows (`proactive_triggers`: `run_at`, kind, subject), enqueued by the scheduler with `FOR UPDATE SKIP LOCKED` like errands, upserted by calendar changes, plus the per-user brief;
   - **user-state transitions** in Valkey: meeting ended, came online, focus ended. These open a *moment*.

   No job iterates over all users.
2. **Pipeline.** `signal → candidate generator (pure, features in code) → hard rules → decide(proactive.value) → [prepare only if kept: a background run, read-only, budgeted] → suggestion(pending) → decide(proactive.moment) at each moment → deliver | defer | digest | drop`. Every drop is recorded with a reason code.
3. **One budget and one quiet-hours rule** for all kinds. Calendar reminders, meeting-soon and errands are kinds of this pipeline.
   - **Insistence:** `explicit` ignores budgets and quiet hours, because the user chose the time; `requested` has its own budget; `initiative` gets ≤ 6 deliveries and ≤ 2 interruptions per day.
   - **Withdrawal:** a cancelled meeting or a finished task withdraws its candidate through its event.
4. **Delivery by *seen*.** Suggestions are durable rows (`agent_suggestions`), and their lifecycle is `pending → scheduled → delivered → seen → acted | dismissed | expired | withdrawn`. `seen` comes from client visibility, not from socket presence. An urgent suggestion unseen after 3 minutes escalates to push or desktop. Replay on `hello` covers every kind.
5. **Feedback is first-class:** act, dismiss with a reason, snooze, mute the kind.
   - **Fatigue (hard rule):** 3 dismissals of a kind in 7 days → that kind drops to `reserved` for 14 days.
   - **Calibration:** outcomes calibrate the value and moment policies (ADR 0026).
6. **Trusted text only in threads.** Text that proactivity writes into a thread is structured server text, with external parts wrapped as untrusted (fixes A5).
7. **Native compatibility.** `explicit` reminders keep `reminder.due` and `reminder.settled` on `/v1/ws/user` and the native `done` and `snooze` routes unchanged. New frames are additive.

## Alternatives considered

| Option | Why not |
|---|---|
| Keep periodic scans and add Jev on top | the scans themselves are the scale problem (P3) and starve users silently; Jev would judge an incomplete candidate set |
| Generate content for every candidate, then judge the text | P7: most generation is wasted; judging features first is cheaper and works without a run |
| Push everything to the chat thread | chat becomes noise; in-context chips and a feed match the new cabinet's workspace, with chat for conversational follow-ups only |
| A workflow engine (Temporal) for triggers and follow-ups | §12 and §19 chose rows run by the scheduler; the draft's Temporal added a third scheduler and duplicate workflows (P4, P6) |

## Consequences

- Load follows activity: ≈ 5 signals/s on average at the design point. There are no per-user scans.
- **Producer slices must emit the listed events**, with ids only. That is a contract item in each package.
- **The cabinet gains three surfaces:** the Leo feed, in-context chips (slots exposed by owner features) and feedback controls. These are absent from the new design today and must be added with the owner.
- Precision and dismissal become measurable. The initial targets are hypotheses, reviewed after 4 weeks.

## Revisit when

- Sustained signals exceed 20 events/s (the §12 relay limit), or a consumer outside the application needs them.
- A scenario needs three or more waiting steps with compensations (§12 revisit trigger for errands).
- Measured precision after calibration stays below 20% → narrow the kinds rather than tune thresholds.
