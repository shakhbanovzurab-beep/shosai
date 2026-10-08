# ADR 0029 — Tools are `ToolSpec`s owned by domain slices; toolsets are routed per turn

- **Status:** accepted by the owner on 2026-10-08.
- **Packages:** S09 (`agent`); core (`core/agent_tools`, `FeatureParts`); every slice that exposes capabilities to Leo.
- **Context documents:** [Leo architecture](../design/leo/ARCHITECTURE.md) §8.1–§8.3; [Leo audit](../design/leo/AUDIT.md) T1, T3–T5, C10, A7, A8; ARCHITECTURE.md §5, inv-14.

## Context

The draft has 130 tools in the agent package (54 read, 74 write, 2 client), plus up to 100 external MCP tools. Their problems:

- **Defined in the wrong place.** They are hand-written JSON-schema dicts without validation. Invalid JSON becomes `{}`.
- **Cross the boundaries.** They import 16+ ORM models of other domains and re-implement router logic. The meetings feature registers its tools by import side effect (C10).
- **Cost on every round.** About 20–25 K tokens of schemas go out per round, up to 12 rounds, with selection by tariff only (T1).
- **Drift and errors.** Previews are computed at proposal time, while execution re-queries later (A8). Results have no global size cap (T4). Egress "reads" spend money and leak data unconfirmed (T5).

## Decision

1. **Contract in core.** `core/agent_tools` holds framework-light types:
   - `ToolSpec`:
     - name (namespaced), toolset, English description, Pydantic `input` and `output`;
     - `effect` (`read` · `egress` · `write` · `client`), `reversibility`, `cost_class`, entitlement, switch;
     - `result_budget`, `timeout`;
     - for writes, `plan` / `preview` / idempotent `execute`;
     - `invalidates`.
   - `ToolContext`: principal, scope, deadline, trace, taint.
   - `PlannedEffect`, `Preview`, `ToolResult`.
2. **Ownership.** A domain slice declares its specs in `contracts.agent_tools` and implements them in its own application layer, under its own transactions and access policy. `FeatureParts` gains `agent_tools`, and composition passes all specs to `agent`. The agent imports no domain slice.
3. **Validation.** Arguments are validated against the input model. A failure returns a typed error result. Truncated tool-call JSON (`finish_reason=length`) is rejected, never executed.
4. **Toolsets.** There are about 14 toolsets of ≤ 8 tools, plus an always-on core toolset (≈ 600 tokens): `workspace.search`, `read_result`, `load_toolset`, `navigate`, `ask_user`. Routing comes from:
   - `decide(turn.route)`;
   - the surface's toolsets;
   - mentioned objects;
   - the last 3 turns (sticky);
   - the skill's toolsets.

   `load_toolset` recovers a miss at the cost of one round. Its rate is a quality metric, with an alert above 5% of turns.
5. **Budgets.**
   - Per round: ≤ 8 parallel calls, each with its own timeout.
   - Per result: the result budget applies. Over budget, a digest goes to the context with `result_ref`, and the full payload stays in the thread for 30 days.
   - Per turn: soft 4 and hard 10 rounds, with the last round tool-less.
6. **Egress.** Web search, image generation and external MCP read-only tools are metered. They require a card when the run's taint is ≥ external.
7. **External MCP tools** are namespaced. Descriptions are sanitised and capped at 500 characters, input schemas at 4 KB, and both are shown at connect time. Non-read-only tools are `write` through the Action Gateway.
8. **MCP exposure (S10)** is a projection of the registry. Writes go through the Action Gateway with `pending_approval`. The persistent-injection sinks are not exposed for writing.

## Alternatives considered

| Option | Why not |
|---|---|
| Keep tools in the agent slice, calling other slices' contracts | the agent becomes the owner of every domain's semantics again; previews and execution drift from the domain's own rules |
| Send all tools, rely on provider prompt caching | 20–25 K tokens still count for latency and for the context window; caching is provider-specific and broken by any change; tool-choice accuracy falls with menu size |
| Retrieval of tools by embedding similarity | misses compositional requests; needs its own index; `turn.route` plus surface signals plus `load_toolset` covers the same need with calibrated probabilities |
| MCP as the internal tool protocol | an extra serialisation and transport inside one process; MCP stays the external interface |

## Consequences

- **Context shrinks.** Typical tool schemas fall from about 20–25 K to about 2–4 K tokens per round.
- **Each slice package grows** by its toolset, its previews and its trajectory evals. The agent owns the contract and the harness.
- **A new core type and a `FeatureParts` field.** `core/agent_tools` must stay free of fastapi, SQLAlchemy and Valkey, like the kernel.
- **Client cache invalidation comes from `invalidates`.** The cabinet no longer mirrors a tool list (audit W2).

## Revisit when

- `load_toolset` exceeds 5% of turns for 2 weeks after calibration → change the toolset partition.
- A model with reliable selection over 100+ tools at negligible marginal cost becomes the default tier → re-measure routing against "send all".
