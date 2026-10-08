# ADR 0023 — Leo is one agent in six separated layers; LangGraph is infrastructure

- **Status:** proposed on 2026-10-08; awaits the owner.
- **Packages:** S09 (agent, decisions, memory, proactive), S11, S05, S10.
- **Context documents:** [Leo architecture](../design/leo/ARCHITECTURE.md) §3–§5; [Leo audit](../design/leo/AUDIT.md) C4, C10; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §5, §18.1.

## Context

In the draft, Leo is one package, `services/agent`, of about 12 000 lines. Its tools reach into the ORM models and services of 16 domains. Decisions about initiative, memory, tool selection and risk are spread across constants, regexes and filters. The principal is assembled in five places with different fields.

The draft's graph itself is sound. It has ten nodes, a side-effect-free `confirm`, a separate `act`, and per-node metrics. The problems are around the graph:

- **Boundaries.** C10 lists 16+ imported ORM models, registration by import side effect and god files.
- **The principal.** C4 shows divergent fields per channel, including a lost hub scope after `/act`.
- **Decisions.** They cannot be measured or calibrated.

The target architecture fixes feature-first slices that meet through contracts (§5) and names LangGraph for agent orchestration (§18.1).

## Decision

1. **Six layers, each answering one question:**
   - Application (channels);
   - Agent Core (run lifecycle, loop, Action Gateway);
   - Decision Layer;
   - Memory and Context;
   - Tools and Skills;
   - Proactive Engine.

   Infrastructure sits underneath. Responsibilities and "never does" rules are in the architecture §3.2.
2. **Slices:**
   - `agent` (core, gateway, threads, runs, context builder, registry, skills runtime, HTTP/SSE);
   - `decisions`;
   - `memory`;
   - `proactive`;
   - `errands`;
   - `models`.

   Domain slices own their tools (ADR 0029).
3. **Clean Architecture inside `agent`.** `domain/` holds the run state machine, action lifecycle, budgets and taint, and it is pure. `application/` holds services behind ports. `infrastructure/` holds the LangGraph graph, the Valkey checkpointer, the event log and the repositories. `channels/` holds the adapters. A new import-linter rule: the `domain` packages of `agent`, `decisions` and `memory` import neither `langgraph` nor provider SDKs.
4. **One `PrincipalFactory`** builds the run principal for every channel: web, voice, MCP, background, errand. Scope (personal, workspace, hub) is part of the principal and is applied to every tool.
5. **One agent.** Specialisation comes from skills (versioned playbooks with their own toolsets) and parallel work from background runs. There are no peer or supervisor agents.

## Alternatives considered

| Option | Why not |
|---|---|
| Keep one `agent` slice that also owns memory, proactivity and decisions | the draft's shape: unmeasurable decisions, one team-sized package, mail triage (S12) could not reuse decisions without importing the agent |
| Multi-agent (supervisor plus specialist agents) | 2–4× model calls per task, hand-off failures, a fragmented "who is Leo"; skills give specialisation at no extra round trip |
| Own agent loop instead of LangGraph | LangGraph is fixed by §18.1 and gives interrupt/resume and checkpoints; keeping it thin and at the edge removes the reason to replace it |
| A separate agent service (own process or image) | §5: one modular monolith, one image; a run is I/O-bound and fits the API role |

## Consequences

- Each layer is testable alone. Decisions are measurable and replayable, and the agent loop shrinks to orchestration.
- Composition gains one more input, `agent_tools`, and `FeatureParts` gains a field (ADR 0029).
- Five slices instead of one: more contracts to keep, offset by import-linter enforcement.
- Draft behaviours worth keeping (AUDIT §3) are re-implemented against the new boundaries, not copied.

## Revisit when

- A skill needs more context or tools than one window holds, or an eval shows a planner/executor split raises task success by more than its token cost.
- A run's CPU share grows enough to disturb the API role's latency (measured event-loop lag > 50 ms p95 attributed to runs).
