# ADR 0069 — The Decision Layer slice: Jev under Leo's consent, rules first, a human reference for every policy

- **Status:** accepted by the owner on 2026-10-26 ([decisions plan](../plan/slices/decisions.md) §2): DL-D2, DL-D3, DL-D4, DL-D6 and DL-D7 as written; DL-D1 decided by the owner's rule once Jev's published terms were compared with those of Leo's models (the plan's §1.4); DL-D5 and DL-D8 with the owner's amendments.
- **Packages:** `decisions` (owner); F6 (a decision's cost row through the deferred-record path; the daily read of OpenRouter's zero-data-retention list); agent (consults `TurnRouter` and `FrictionJudge`, a new `InjectionJudge` port, reports outcomes, a card's `suspicious` field); the cabinet's `leo` feature (the card's wording); later memory, proactive, mail, hubs and studio (their points).
- **Context documents:** [decisions plan](../plan/slices/decisions.md); [Leo architecture](../design/leo/ARCHITECTURE.md) §3.2–§3.3, §6, §7.4, §10, §11, §13.1, §17 Q-3; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §8, §9 (inv-9, inv-12), §22; [ADR 0026](0026-leo-decision-layer-on-jev.md); [ADR 0068](0068-leo-agent-slice.md) AG-D7, AG-D8.

## Context

ADR 0026 made Leo's judgement calls one layer of versioned policies over Jev, with deterministic rules and fallbacks, records and calibration. Planning the slice against the code and documents as they stand left questions it did not settle:

- **Personal data.** Every live question carries a person's text, while the Leo architecture (§17 Q-3) and the target architecture (§22) waited for a legal review of TypeSafe AI before Jev could read any.
- **Latency.** F6's port writes a call's cost row inside the call, in the payer's home: for a Russian-home person ≈ 90–135 ms on top of Jev's 160–300 ms, inside deadlines of 300–400 ms.
- **What each point does now.** Every toolset still fits the routing budget, the agent never handles a refusal, and the `suspicious` taint changes no card yet.
- **Operations and data.** No screen exists for policies; records need a shape that serves calibration without personal data; labelled data cannot come from people's conversations.

## Decision

1. **Jev reads personal data under Leo's cross-border consent (DL-D1).** The owner's rule: if Jev's published terms on training, retention and region are not worse than those of Leo's main models through OpenRouter, Jev works under the same consent (nfr-14) and is enabled after its calibration and two weeks of shadow, without a separate legal gate. Compared on 2026-10-26:
   - **Training.** TypeSafe does not train on inputs or outputs, the same as the best of the main models.
   - **Retention.** Jev's only endpoint is on OpenRouter's zero-data-retention list. Gemini 3.8 Flash is on it only through Vertex, Claude Haiku 5.5 only through Vertex and Bedrock, and Shosai's calls do not require ZDR, so Leo's answers may land on endpoints that keep prompts. Jev is stricter here.
   - **Region.** The same kind of transfer: out of Russia, to endpoints not pinned to the EU.

   The verdict is that Jev is not worse. The comparison is kept true by a daily read of the ZDR list (amended in step 3: the read is this slice's task over core's OpenRouter wire, its answer kept in Valkey three days): off the list, or unread for three days, every point runs its rule (`not_zdr`) and an alert opens.
2. **The person pays for a decision, as background work, off the hot path (DL-D2).** The cost row is in the person's home under the feature `decisions.<point>`, with origin `background`: inside their background budget, outside their Leo tokens. F6 hands a `decide` call's cost row to the deferred-record path (inv-9 holds) instead of writing it inside the call.
3. **`turn.route` ranks only the room the rule leaves (DL-D3).** It is not asked while every allowed toolset fits. Toolsets it brings in stay for three turns, so the prompt prefix stays cacheable. Skill, tier and clarify questions come with studio and the `ask_user` UI.
4. **`action.friction` may only turn a standard card into a warning (DL-D4).** It is asked only when the rule says standard. "Refuse and explain" is not used.
5. **`content.injection` judges every piece of text that enters a run under an untrusted label, the person's uploads and attachments included (DL-D5, amended by the owner).** Only the text the person wrote themselves is not judged: their messages to Leo, their notes, their tasks. Judgements run off the round's path and are awaited before a write's card and at the run's end. A suspicious run's card says so in plain words.
6. **Policies are operated by `shosai decisions` on the host (DL-D6).** It covers dataset checks, calibrate, report, promote and retire, with Grafana panels and no admin screen.
7. **Records (DL-D7).** Every consulted decision is a row of `agent_decisions`: ids, numbers, codes, a keyed hash of the state, no person id and no text. Rows are written in batches per home and expire with their monthly partitions. The consumer reports the outcome it observes into `agent_decision_outcomes`. Reliability per band is aggregated daily, as counts, into the EU home.
8. **Synthetic sets checked against a human reference (DL-D8, amended by the owner).**
   - **Synthetic sets** are generated per language (never translated), labelled by construction and cross-checked by a second model, with ≥ 50 examples per band and language.
   - **The reference set** has at least 50 cases per point in Russian and 50 in English. The cases are realistic, never a person's data, and are labelled blind by the owner or a person the owner names.
   - **Checking synthetic against the reference.** The generator's labels agree with the human ones on ≥ 90% of the reference. A policy's accuracy on the reference is within 10 points of its synthetic accuracy and at least its floor, and its careful outcome is found at no less than the floor.
   - **Release.** Promotion to shadow or active requires every gate. CI checks the gates on recorded probabilities.

## Alternatives considered

| Option | Why not |
|---|---|
| Keep live Jev off per home until the legal review (`DECISIONS_JEV_HOMES`, the plan's first proposal) | Jev's published terms are no worse than those of the models Leo already sends the same text to under the same consent; waiting would hold back calibration without lowering any risk the consent does not already cover |
| The platform account pays for decisions | The fast EU-home row comes at the cost of per-person attribution, and consent would have to be checked apart from the payer |
| The cost row inside the call (F6 as built) | Russian-home decisions would mostly miss their deadlines and fall back |
| The full `turn.route` point now | It adds Jev's latency to every turn while every toolset fits, and tier routing would decide what a person's frontier allowance buys without a billing decision |
| "Refuse and explain" for friction | Nothing runs without the person's approval already; a false refusal costs trust and a retyped request |
| Judge only text from others, not the person's files | Uploaded documents and attachments are usually someone else's text; an injection in them is as dangerous |
| Pull outcomes from each consumer's tables | One more reader port per consumer, and a cycle between contracts once memory and proactive both use and feed decisions |
| Synthetic data only | Labels by construction can drift from human judgement unnoticed; a small human reference catches it before release |

## Consequences

- The layer ships whole and acts as soon as each policy passes its gates and shadow; until then every point runs its rule, recorded.
- Two small F6 changes: the deferred cost row for `decide`, and the daily ZDR read with its ticket.
- The agent changes in narrow places: two ports consulted, one new port, outcome reports, an additive card field. The cabinet gains one line of card wording in 16 languages.
- A person labels about 100 reference cases per point, the three points of this plan first.
- Records add ≈ 3.8 GB per 90 days at 10 000 DAU and Jev ≈ $10 a day; no new store.
- The Leo architecture's §17 Q-3 is closed; the target architecture's §22 keeps Jev only within the general review of AI providers as subprocessors.

## Revisit when

- Jev's endpoint leaves OpenRouter's ZDR list, or TypeSafe's terms change: repeat the comparison before enabling it again.
- A policy's online precision stays below its rule's for 4 weeks (ADR 0026): that point returns to its rule.
- Warned cards are approved as often as standard ones: friction's questions, or "refuse and explain", are reconsidered with the data.
- The toolset catalog makes `load_toolset` exceed 5% of turns while `turn.route` is active: its questions are reconsidered.

## As built (steps 5–8, 2026-10-27)

Refinements the implementation needed, decided by the agent within this decision and recorded in the plan's step rows:

- **`turn.route` is asked only when a toolset cannot be offered even for reading.** Since the agent's reads-first rule, a person's catalog no longer fits segment 2 whole (≈ 7 300 tokens against 4 000; its reads ≈ 3 500), so "asked when the rule defers" would mean most turns. Keeping DL-D3's "no call, no cost, no latency today", the router waits until reads overflow; ranking writes too is an open question for the owner.
- **The agent's ports carry what the decision needs.** `TurnRouter` reads a `RouteRequest` (candidates with their tools' registered first sentences, the question, the last answer's start, the page, the turn count, the scope, consent and run) rather than an additive `question` on the rule's `RouteFacts`; `FrictionFacts` carries the rendered card and the action's id; `InjectionPiece` carries the text as written, without the wrapper's markers, and the piece's number.
- **A run's final taint is kept** (`agent_runs.taint`), so "ready for memory's admission" has a place to be ready in; the card's additive `suspicious` field states a suspicious run.
- **A committed set is held to its report, not to the gates.** `calibrate` writes `report.json` beside the recorded run; CI checks every committed case is answered under the current wording and the report is the run's. Only `promote` requires passing gates, since sets are committed before a person labels their reference, and a step may end with a failing gate recorded.
- **Reference drafts are never filtered by the labeller,** whose agreement with the person is what the reference measures.
- **Reliability counts keep the shadow flag** beside the planned key, so a shadow revision's counts never mix with the active one's.
- **The tickets are objectives over `shosai_decision_requests_total`**; the rule generator renders only the burns an objective's share can reach.
