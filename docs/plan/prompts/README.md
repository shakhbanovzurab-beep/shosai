# Agent prompts

One file per work package of [the rewrite plan](../REWRITE_PLAN.md). Start a new session in `/root/whisperer-v2` with `claude --add-dir /root/whisperer` and paste the package's launch line from the plan, section 6.

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
