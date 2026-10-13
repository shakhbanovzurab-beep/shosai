# Backend — next step

Follow the common protocol in `docs/plan/prompts/README.md`. Two prerequisites; if either is missing, stop and say which:

- `docs/plan/audits/F1-audit.md` with the owner's decision recorded (keep and fix F1, or rebuild the foundation);
- `docs/plan/SLICE_MAP.md` approved by the owner, with the slice rows in STATUS.md replaced by its cut.

**One session does exactly one step** of one package or slice plan, then stops. The user starts every session with the same launch line; this prompt decides what the session does.

## 1. Choose the step

Read `docs/plan/STATUS.md` and walk the backend path in this order:

1. The foundation work the F1 audit decision calls for.
2. **F6** platform services, in the steps of its plan; steps that need a slice wait for it.
3. The slices in the build order of `docs/plan/SLICE_MAP.md`, preferring, among those whose dependencies are `done`, the one that unblocks the most others.

Skip a package that is `done`, `blocked`, or whose dependencies in STATUS.md are not `done`, and say why you skipped it. Packages that need the owner's resources (F4, F5 step 7, M1, M2) are not on this path.

In the first package that remains:

- **It has no plan yet** (`docs/plan/packages/<ID>.md` for F packages, `docs/plan/slices/<name>.md` for slices) → this is a **planning session**: follow the package prompt (`docs/plan/prompts/<ID>-*.md`, or `S-feature-slice.md` for slices) and write the plan. No application code. Stop for the user's approval.
- **The plan exists** → take its first step that is not marked done. This is an **implementation session**.

Before any work, tell the user in three lines: the package, the step, and its "Done when". If two steps are equally next, or the plan's order no longer fits the code, ask instead of choosing.

## 2. Load the skills

Load `fastapi` and `python-doctor`, every skill in the step's **Skills** column, and the mandatory skills of every other zone the step touches (CLAUDE.md "Mandatory skills"). Read the target architecture sections the step names. Load them before reading the draft.

## 3. Implement the step

- Only what the step's row says. Work that belongs to a later step stays for that step; anything you find that is out of scope goes into your report, not into the code.
- Read the draft in `/root/whisperer` for behaviour and contracts only; structure and rules come from CLAUDE.md and the target architecture.
- Tests ship with the step and prove its "Done when".
- Stop and ask on any decision CLAUDE.md, the target architecture, the plan and the draft do not settle; propose an answer with its trade-off.

## 4. Verify

From `backend/`: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run pytest`, and `uv run python-doctor . --score` → `100`. Run the frontend gate too if the step touched `frontend/`. The test databases are left clean. Report a failing check as a failure.

## 5. Close the session

1. Mark the step done in its plan with a one-line result; update the package's row in STATUS.md (`in progress`, or `done` after the last step).
2. Report: what changed, what was verified, what is open, the skills loaded and any recommendation not followed, with the reason.
3. Wait for «Принято», then commit the step as one atomic commit with explicit paths and push it (CLAUDE.md "Git workflow").
4. End with one line: the next step this prompt will pick, so the user knows what the next session does.

Do not start the next step in this session, even if time remains.
