# decisions

Leo's Decision Layer: the judgement calls the rest of Leo must not make by hand — which toolsets a turn needs, how carefully a card asks, whether text entering a run tries to instruct the AI, and later what to remember, whether and when to speak first, which mail needs the person — answered as typed outcomes of versioned policies over Jev, a calibrated decision model, behind deterministic rules that only ever make an outcome more careful. The slice has no screen and no route.

- Plan: [docs/plan/slices/decisions.md](../../../../../docs/plan/slices/decisions.md). Decisions: DL-D1…DL-D8 in the plan and [ADR 0069](../../../../../docs/adr/0069-decision-layer-slice.md); the design is the [Leo architecture](../../../../../docs/design/leo/ARCHITECTURE.md) §6 with [ADR 0026](../../../../../docs/adr/0026-leo-decision-layer-on-jev.md).
- Public surface: `contracts` — the port `Decisions` under `DECISION_LAYER` (`decide`, `observe`) and its typed points `TURN_ROUTE`, `ACTION_FRICTION`, `CONTENT_INJECTION`, each with its facts, outcome and observation.

## Policies (step 1)

- A policy (`domain/policy.py`) is one version of a point: its English questions to Jev, the signal each answer gives and the cut it is read through (`domain/verdicts.py`: a threshold with a margin either side where the verdict is unsure), the JSON state Jev reads within its budget (`domain/state.py`: facts computed in code, text in named string fields cut head and tail by their escaped size), the facts a record keeps, and how verdicts become an outcome. `careful(rule, judged)` keeps the final outcome no less careful than the consumer's rule; `settled` says when the rule's answer cannot change, so nothing is asked.
- Thresholds are not in the code: calibration (`domain/calibration.py`) fits each cut for a target precision of one side, with an unsure verdict joining the side its policy reads it as, and measures expected calibration error and accuracy.
- `turn.route@1` (`domain/policies/turn_route.py`): one `noul` per toolset the rule could not fit — is any of its tools needed — and the surely needed ones come first, by probability; never asked while every toolset fits (DL-D3).
- `action.friction@1` (`domain/policies/action_friction.py`): asked only when the rule left a card standard; it warns unless the action surely matches the request and surely stays narrow (DL-D4).
- `content.injection@1` (`domain/policies/content_injection.py`): one `noul` per piece of text under an untrusted label — uploads and attachments included, the person's own words never — and anything but a sure "no" makes the run suspicious (DL-D5).
- Records (`domain/records.py`) keep ids, numbers and codes — the subject, the facts, a keyed hash of the state, the probabilities, the rule's and the final outcome, reason and source — never text and no person's id (DL-D7).
- Every question's wording is registered in the model-facing English test (`policy_wording`).

## Tables (step 2)

- In each home (`infrastructure/records.py`): `agent_decisions` — one row per consulted decision — and `agent_decision_outcomes` — what followed a subject — in monthly partitions kept four months. Neither has a person's id, so no row-level policy: the application may only insert, the sweep role reads them for the daily reliability pass. The database keeps every code closed (point, subject, reason, source, language, outcome) and a state hash at 16 bytes.
- In the EU home: `decision_thresholds` — a version's fitted cuts per revision with its calibration report, numbers only — and `decision_policies` — the version in `shadow`, `active` or `retired` and the revision it uses; unique indexes hold one active and one shadow version per point, and a version in force always names an existing revision. The application reads and adds, and changes a state, never deletes.
- The account data declaration lists both home tables as `expires`: nothing in them outlives its partition, and nothing identifies a person.

## The engine (step 3)

- `DECISION_LAYER` is bound to `application/engine.py`: the point's versions in force (`application/in_force.py`, read from the EU home at most once a minute, the last good copy kept, a stored version whose wording differs from the code's never used); pre-rules — nothing to decide (counted only), a state over budget, no cross-border consent in the Russian home, the process's calls in flight at `DECISIONS_MAX_IN_FLIGHT`, Jev's endpoint not confirmed zero-retention — each the rule's outcome with its reason, recorded; then Jev.
- Jev is asked through the provider port (`application/asking.py`): paid by the person as background work (outside their Leo tokens), effect key `decision:<id>`, the port's deadline three times the policy's (≤ 2 s). The caller waits only the policy's deadline; a later answer lands, is paid once and recorded as `late`. The port hands the call's cost row to the record task (`CostWriter.later`): a decision makes no round trip to the payer's home (7 before, measured; ADR 0069 DL-D2).
- Verdicts, the policy's outcome and the more careful of it and the rule's (`application/judging.py`); a policy that would soften the rule is overruled and counted (`shosai_decision_unsafe_outcomes_total`).
- A shadow version acts on nothing: with the active one's questions it is judged on the same answer under its own cuts, otherwise it asks on its own in the background; alone, the caller gets the rule at once (`application/recording.py`).
- Records and observations go through `infrastructure/record_writer.py`: buffered per home and table, one insert per batch every second or at 500 rows, the rest on stop; a batch a home refuses, or a row past the buffer's cap, is counted lost. On stop the engine first lets its calls in flight land (`drain`).
- The daily task `decisions.check_zero_retention` (EU home) reads OpenRouter's public zero-data-retention list and the pinned model's endpoints (`core/ai/adapters/openrouter_endpoints.py`) and keeps the answer in Valkey for three days (`infrastructure/provider_terms.py`); a status that is not a fresh "yes" makes every point run its rule (`not_zdr`), shown by `shosai_decision_zero_retention`.
- A record's state hash is an HMAC under a key derived from `FERNET_KEY` (`infrastructure/state_key.py`); without the key, records carry none.
- Settings (`settings.py`): `DECISIONS_JEV_MODEL` — the pinned snapshot, never an alias — and `DECISIONS_MAX_IN_FLIGHT`.
