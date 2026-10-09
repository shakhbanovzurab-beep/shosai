# Agent prompts

One file per work package of [the rewrite plan](../REWRITE_PLAN.md). Start a new session in `/root/shosai` with `claude --add-dir /root/whisperer` and paste the package's launch line from the plan, section 6.

Every prompt relies on:

- `.claude/CLAUDE.md` — loaded automatically in every session;
- [REWRITE_PLAN.md](../REWRITE_PLAN.md) and [STATUS.md](../STATUS.md);
- the common protocol below, which every prompt includes by reference.

## Common protocol

Every agent follows these steps, in addition to its package prompt.

1. **Orient.** Read `docs/plan/REWRITE_PLAN.md`, `docs/plan/STATUS.md`, and the sections of `docs/design/ARCHITECTURE.md` that your package touches. Check `git status` and `git log -5`; parallel sessions may be working in the same tree.
2. **Check dependencies.** If a package you depend on is not `done` in STATUS.md, stop and tell the user which one is missing.
3. **Load the skills.** Before reading draft code or designing anything, invoke with the Skill tool every skill your package prompt names and every mandatory skill of each zone you will touch (CLAUDE.md "Mandatory skills"). When the work reaches a new zone, load that zone's skills before continuing. Use the skills' recommendations as the standard for your design and code.
4. **Work only in your package's paths.** Edits to shared registration points (router, composition root, navigation, locale bundles, CI) are small and additive.
5. **Read the draft, do not copy it blindly.** `/root/whisperer` is read only. Take behaviour, texts, contracts and visuals from it; take structure and rules from CLAUDE.md and the target architecture.
6. **Stop and ask** when you reach a decision that CLAUDE.md, the target architecture and the draft do not settle, or one listed in section 5 of the plan. Propose an answer with its trade-off.
7. **Verify** with the checks from CLAUDE.md for the zones you changed, plus your package's definition of done. Check the change against every loaded skill. Report failures as failures.
8. **Update STATUS.md**: your row's status, the link to your package plan if you wrote one, and a one-line note.
9. **Report and wait.** Summarise what changed, what was verified and what is open, and list the skills you loaded and any skill recommendation you did not follow, with the reason. Commit and push only after the user says «Принято», with explicit paths, following CLAUDE.md "Git workflow".

## Session mode for multi-session packages

A package whose prompt says it is multi-session is too large for one session. The user starts it with the same launch line every time; the package plan in `docs/plan/packages/<ID>.md` tells each session what to do. Feature slices follow the same idea with their own plan path (`S-feature-slice.md`).

- **No package plan yet → planning session.** Read the inputs the prompt names, then write `docs/plan/packages/<ID>.md`:
  - the facts the plan rests on, with sources;
  - the design: structure, public interfaces, how the target architecture's rules are met;
  - the decisions the user must take, each with a proposed answer and its trade-off; record the confirmed ones as ADRs;
  - a **Steps** table with the columns `Step | Content | Skills | Done when`. Each step fits one session, leaves the project working, and has its own checks.

  Write no application code in this session. Set the status to `planned` in STATUS.md once the user approves the plan.
- **Plan approved → implementation session.** Take the first step of the plan that is not marked done. Implement it, verify it, mark it done in the plan with a one-line result, set STATUS.md to `in progress` (`done` after the last step), report, and stop. Do not start the next step in the same session.
- **Every step ends releasable.** A step is a task in the sense of CLAUDE.md: its checks and the zone's gates pass at its end, and after «Принято» it is committed and pushed, so CI on `main` stays green.
- **A session stopped by a usage limit** is resumed in the same session after the limit resets — write «продолжай» — instead of starting a new one, so the step's context is not lost.
