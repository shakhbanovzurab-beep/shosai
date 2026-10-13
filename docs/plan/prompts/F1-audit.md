# F1 audit — keep, fix or rebuild the backend foundation

Follow the common protocol in `docs/plan/prompts/README.md`. **One session. No code changes**: the output is a report and a recommendation; the owner decides.

## Why

F1 (backend foundation) was built on 2026-10-02. Since then the product changed course:

- the web split into a Next.js site and a Vite cabinet (2026-10-07, ADR 0021, 0022);
- the Leo architecture was accepted (2026-10-08, `docs/design/leo/ARCHITECTURE.md`, ADR 0023–0033);
- platform services were planned (F6, ADR 0034–0036) and the product was renamed to Shosai (ADR 0037);
- the owner set the philosophy (CLAUDE.md "Philosophy") and decided that Shosai is built **from scratch**: the draft is a reference, not a specification; only shipped native clients keep their contract (CLAUDE.md "Goal").

The owner is inclined to rebuild the backend from scratch. This audit establishes whether F1 already is what a from-scratch build would produce, and what in it would differ.

## Load first

`fastapi`, `python-doctor`, `agent-architecture`; the four Docker skills (CLAUDE.md "Mandatory skills") before reading Compose and Dockerfiles; `data-storage`, `consistency-coordination`, `resilience-failure` and `task-scheduling` for the matching parts.

## Read

- CLAUDE.md in full, as it is today.
- `docs/design/ARCHITECTURE.md` in full; `docs/design/leo/ARCHITECTURE.md` in full.
- Every ADR; for ADR 0008–0016 (F1's own decisions) check that their reasons still hold.
- `docs/plan/packages/F1-backend-foundation.md`, `docs/plan/packages/F6-platform-services.md`, `docs/plan/STATUS.md`, `docs/plan/FEATURE_MAP.md`.
- `backend/` in full, `compose.dev.yaml`, `docs/development.md`, `.github/workflows/ci.yml`.

## Check

1. **Architecture.** Every part of F1 against the target architecture: the two homes and home-aware access, tenancy scope and RLS, the one bucket, Valkey, tasks and the broker, outbox and events, process roles, settings, observability, errors. Name each place where F1 and the document differ, and which one is right.
2. **Leo.** What the Leo architecture needs from the foundation (kernel contracts, `FeatureParts`, agent tool contract, effects and idempotency, decision records, memory stores, background budgets) and whether F1 provides it, blocks it, or leaves it cleanly to F6 and S09.
3. **Draft carry-over.** Anything in F1 that exists only because the draft had it, and is not demanded by the architecture or by a native client. In particular: the route snapshot and the "D1 gate over the composed apps" — under the new goal only native routes (and external integrations' callbacks) must stay compatible, so a gate over the whole draft route table is wrong.
4. **Engineering rules.** CLAUDE.md engineering rules and stack table: versions, async, typing, error handling, logging, configuration, file length, feature-first layout, import-linter contracts. Run the backend gates (`ruff`, `mypy`, `lint-imports`, `pytest`, `python-doctor --score`) and report their real output.
5. **Quality of what is there.** Overengineering, dead code, abstractions without a second user, tests that test nothing; and the opposite — missing parts a from-scratch build would have.
6. **F6 plan.** The F6 plan was written on 2026-10-09 under the old goal. Mark which of its parts rest on the draft's behaviour (thresholds, admin paths kept for the draft's screens, dropped routes) and must be re-derived from the product.

## Output

Write `docs/plan/audits/F1-audit.md`:

- **Findings**, each with evidence (file and line, document and section) and a class: `keep` · `fix` (with the change and its size) · `remove`.
- **Estimate** of the work for both options: fix F1 in place, or rebuild the foundation from an empty `backend/`. Count what each option repeats, risks and gains.
- **Recommendation** with its reasons, and the list of decisions the owner must take.
- **Next steps** for the chosen option, sized for one session each.

Do not change code, plans, ADRs or STATUS.md in this session. Report, list the skills you loaded, and wait for the owner's decision. Commit the audit only after «Принято».
