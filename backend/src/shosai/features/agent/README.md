# agent

Leo's core: a person's conversations with Leo in Personal and in each workspace, the run that answers a turn — reading through every slice's tools under the one access policy and naming each source with its space — and the Action Gateway, the only path by which Leo changes anything, after the person approves a card that says exactly what will change. The slice also owns Settings › Leo, the rating of answers, the skills store, the native model proxy of the shipped desktop clients and Leo in the admin panel. The cabinet's feature is `leo` (SLICE_MAP §4.3).

- Plan: [docs/plan/slices/agent.md](../../../../../docs/plan/slices/agent.md). Decisions: AG-D1…AG-D14 in the plan and [ADR 0068](../../../../../docs/adr/0068-leo-agent-slice.md); the design is the [Leo architecture](../../../../../docs/design/leo/ARCHITECTURE.md) with ADR 0023–0033.
- Public surface: `contracts` (`ActionProposals` for a slice's planned write without a model round; the ports agent needs — `TurnRouter`, `FrictionJudge`, `MemoryRecall`, `ProfileFacts` — and `SkillReader` for studio) and `contracts.events` (`agent.turn.completed`).
- Turns run on the dedicated `agent` queue's workers; the API admits, commits and streams them from the run's log in Valkey (AG-D12). LangGraph is only the frame of a turn (AG-D14).

## Rules the domain holds

- `domain/threads.py` — a thread's scope (Personal, a workspace or a hub), titles of 1–120 characters, a question of 1–4 000 characters with up to five attachments, "Regenerate" and "Edit" on the last question only; a departed workspace's threads erased 7 days after the departure unless the membership is active again (AG-D3).
- `domain/runs.py` — a run is running, paused or ended once (completed, failed with a code, cancelled); deadlines, the thread lease, the event log, two runs per person and 48 per worker.
- `domain/actions.py` — an action's machine (Leo §8.4): every transition names the status it expects, so the store applies it as one conditional update with one winner; items end with honest partial success, and a cut item is `outcome_unknown`, never retried; a proposal expires after an hour; the cabinet sees an approved action as executing and a superseded one as expired.
- `domain/budgets.py` — the context's eight segments with their caps, from the most static to the most volatile; four rounds before Leo is asked to conclude, ten at most, eight calls a round; token estimates from UTF-8 bytes in every language; the recent window cut by tokens; compaction past 70% of it.
- `domain/wrapper.py` — untrusted text between a per-run boundary and a closing marker, labelled from a closed set and escaped so it holds no `<<`; the run's taint only grows, and external text makes egress wait for a card.
- `domain/sources.py` — the run's sources numbered in arrival order; a number never changes and the same place in the same thing keeps its number (AG-D1).
- `domain/stream.py` — the stream's closed vocabulary, monotonic numbers, steps opened and closed once, exactly one terminal event.
- `domain/routing.py`, `domain/friction.py` — the deterministic rules until `decisions` binds its ports (AG-D7): core, the page's and the thread's recent toolsets, then others while segment 2 holds; a warning card for a tainted run or an irreversible write, never less than the rule.
- `domain/preferences.py` — Settings › Leo with everything on by default, `auto` model and language, the switches gating tools, the four switches of the native `/v1/auth/me`.
- `domain/feedback.py` — a rating of an answer; a rated turn kept as an evaluation case only with `improve_models` consent and no workspace source, the name masked, a year at most (AG-D13).

Core's tool contract gained, for this slice (ADR 0068): `ToolResult.sources` and `.artifacts` (`core/agent_tools/sources.py`), `ToolSpec.step_detail` and a write's `ToolSpec.previews` — its wording of the preview keys in the 16 languages, rendered by `core/agent_tools/previews.py` into the card's title and rows.
