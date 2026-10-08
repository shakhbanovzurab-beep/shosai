# ADR 0026 — A Decision Layer of versioned policies over Jev, with deterministic rules and fallbacks

- **Status:** proposed on 2026-10-08; awaits the owner. **Adds** a provider to [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.2 and §18.2 and a legal item to §22.
- **Packages:** S09 (new slice `decisions`); F6 (provider port gains `decide`); used by S09 `agent`, `memory`, `proactive`, and by S12 (mail triage).
- **Context documents:** [Leo architecture](../design/leo/ARCHITECTURE.md) §6; [Leo audit](../design/leo/AUDIT.md) P1, P2, M5, T1; ARCHITECTURE.md nfr-7, nfr-14, inv-9, §14 rule 4.

## Context

In the draft, Leo makes judgement calls in many places, each by a different mechanism, and none can be measured:

| Judgement | Draft mechanism |
|---|---|
| speak now? | static urgency per kind; ignores the stored confidence (`restraint.py:34`) |
| which tools? | tariff filter only; all 130 schemas every round (`registry.py:225-241`) |
| remember this? | a 16-language regex and word lists (`memory_link.py:54-83`, `salience.py`) |
| is this mail important? | threshold rules (`importance.py`) |
| how risky is this action? | nothing beyond the destructive flag |

The owner asked for **Jev** as a separate decision layer. Jev (TypeSafe AI, released 2026-09-15) is a decision model, not a chat model:

- **Request:** typed questions (`choice`, `score`, `noul`) about a state.
- **Answer:** calibrated probabilities with a `confidence`. No text, no tools, one round trip.
- **Access:** OpenRouter's Decisions API (`/api/alpha/decisions`), model `typesafe/jev-1.13`.
- **Price:** about $0.042 per M input tokens; output is free.
- **Latency:** published measurements of ≈ 160–300 ms.
- **Limits:**
  - not deterministic between calls;
  - weak at arithmetic and negation;
  - 32 K context;
  - language coverage, retention and DPA not published on the pages read.

The brief names "Jev from TypeScript AI". TypeScript appears only in Jev's SDKs. The backend stays FastAPI-only ([ADR 0021](0021-public-site-on-nextjs-cabinet-on-vite.md)), and Jev is an HTTP API callable from Python.

## Decision

1. **New slice `decisions`** with one port: `decide(point, subject, features, snippets) → Outcome{value, reason_code, source, policy_version, decision_id}`. Callers name a decision point; they never call Jev directly.
2. **Policies are code**, versioned (`turn.route@3`), reviewed, and registered in the model-facing English test. Each declares:
   - feature schema, questions;
   - band → outcome map;
   - hard pre-rules and post-rules;
   - fallback rule, deadline, shadow eligibility.

   Thresholds are platform data (`decision_thresholds`, EU home, §6), versioned per policy.
3. **Monotonic safety.** Hard rules (settings, consent, quiet hours, budgets, entitlements) run before and after the model, and can only make an outcome more conservative. Jev never decides confirmation (effect class, ADR 0025), access (inv-14) or text.
4. **Jev through the F6 provider port** (`decide`). It is metered with an effect key (inv-9), behind a breaker and the provider semaphore, with the snapshot pinned and a contract test on the response shape.
5. **Features are computed in code** (times, counts, ages), and text snippets are bounded (≈ 2 K tokens) and untrusted-wrapped. Answers map to outcomes through **bands with margins**, never exact values. A decision is recorded once and reused.
6. **Fallback for every policy**, used on timeout, error, contract mismatch or missing cross-border consent (nfr-14). The fallback is the conservative deterministic rule: the draft's `restraint` and `importance` rules for initiative and mail, full routing for tools, "store only explicit requests" for memory, "screen-only approval with warning" for friction.
7. **Language.** A policy is enabled only after its evaluation passes in all 16 platform languages. Otherwise it runs on its fallback for everyone; no branch depends on language.
8. **Records.** `agent_decisions` (home DB, monthly partitions, 90 days) holds point, version, subject ref, features, state hash, probabilities, outcome, source, latency, cost and the provider request id. It never holds state text.
9. **Calibration:**
   - offline on labelled synthetic sets in 16 languages, with the gates ECE ≤ 0.05 and a per-language accuracy floor;
   - shadow versions on live traffic before promotion;
   - online reliability curves from decision records joined with user outcomes (acted, dismissed, approved, rejected).
10. **First decision points:**
    - `turn.route` (toolsets, skill, tier, clarify);
    - `action.friction`;
    - `content.injection`;
    - `memory.admit`;
    - `proactive.value`;
    - `proactive.moment`;
    - `mail.triage`.

## Alternatives considered

| Option | Why not |
|---|---|
| Decisions inside the agent loop by the generative model | 10–100× the cost and seconds instead of milliseconds per decision; no calibrated probability; cannot run when no run exists (initiative, triage) |
| Deterministic rules only (draft) | P1: no per-instance value, no attention, no learning; brittle multilingual word lists (M5) |
| A TypeScript decision service (a JevPolicy-style runtime) beside the backend | a second runtime and image against §5 and ADR 0021; an extra network hop on the hot path; the HTTP API is callable from Python as is |
| A fine-tuned in-house classifier | needs labelled data that does not exist yet; Jev plus calibration is the bootstrap; the exit path below keeps this open |
| Calling Jev directly from each feature | no versioning, no records, no fallback discipline, bypasses the provider port (inv-9) |

## Consequences

- Each judgement becomes measurable, versioned, replayable over past probabilities, and cheap: ≈ $19/day at the design point.
- **Latency budget.** `turn.route` runs in parallel with the embedding call, so it adds no critical-path time if it stays under ≈ 300 ms. Its deadline is 350 ms, then fallback.
- **New external dependency.** TypeSafe AI must be added as a subprocessor (§22). Until that review, Jev runs only on synthetic data and in shadow on features without text.
- **Exit path.** Open-weight decision models (Laya, Kev) speak the same `/v1/systemone` shape through Ollaya, so self-hosting is a provider-port configuration plus an evaluation.

## Revisit when

- Jev's contract changes incompatibly, or its availability on the alpha endpoint falls below 99.5% in a month → move to TypeSafe's own endpoint or a self-hosted model.
- A policy's online precision stays below its fallback's for 4 weeks → that policy returns to rules.
- Labelled outcome data per point exceeds about 50 000 examples → evaluate an in-house model against Jev.
