# ADR 0020 — react-doctor score from the vendor's service

- **Status:** accepted by the owner on 2026-10-02 (F2 step 1).
- **Package:** F2, frontend foundation (`frontend/package.json`, CI job `frontend`).
- **Context documents:** [CLAUDE.md](../../.claude/CLAUDE.md) "Checks"; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §18.2; [F2 plan](../plan/packages/F2-frontend-foundation.md) §1.3.

## Context

- The frontend gate is `npm run doctor -- --score` printing `100`, with react-doctor pinned at 0.9.14 (§18.2). The F2 plan required step 1 to check that it runs offline and sends nothing in CI.
- Checked on 2026-10-02 by intercepting every request of a run:
  - **The score is not computed locally.** react-doctor posts the findings to `https://www.react.doctor/api/score` and prints what the service answers. The body holds every finding (rule, file path, line, message), the repository name, the commit, the framework, the React version, the number of source files and, in GitHub Actions, the event name. Without network it prints "Score unavailable" and no number; `--no-score` (alias `--no-telemetry`) removes the request together with the score.
  - **Supply-chain scan:** one request per dependency (name and version) to `firewall-api.socket.dev`.
  - **Telemetry:** OTLP metrics and traces to Axiom, crash reports to Sentry. `REACT_DOCTOR_NO_TELEMETRY=1` turns both off and keeps the score; no configuration key does.
  - Where the GitHub CLI `gh` is installed and signed in, react-doctor asks the GitHub API for the user's permission on the repository and adds it to the score request. CI passes no GitHub token to the step.
- With `--no-score --no-supply-chain` and the variable set, a run makes no request and still lists every finding; the gate would then be "zero findings" instead of a score.

## Decision

1. The gate stays as CLAUDE.md states it: `npm run doctor -- --score` prints `100`, scored by the vendor's service.
2. The supply-chain scan through Socket.dev stays on.
3. Telemetry is off: the `doctor` script runs react-doctor with `REACT_DOCTOR_NO_TELEMETRY=1`. Every run, local or in CI, goes through that script.

## Consequences

- Every run sends the list of findings, the repository name and the commit to react.doctor, and the dependency list to Socket.dev. File contents are not sent; a finding carries its file path, position, message and help text, and a message can quote a name from the code.
- The gate needs network. When the score service is down or unreachable, the score is empty and the CI step fails; rerun the job once the service is back.
- The vendor can change how it scores without a new react-doctor version, so the same commit can score differently over time. A change of score with no change of code or version points there first.
- No traces, metrics or crash reports of the tool leave the machine.

## Revisit when

- react-doctor computes the score locally again, or the service changes what it collects.
- The repository becomes public or the findings could reveal something confidential; then switch to the offline gate (`--no-score --no-supply-chain`, pass on zero findings) and update CLAUDE.md "Checks".
