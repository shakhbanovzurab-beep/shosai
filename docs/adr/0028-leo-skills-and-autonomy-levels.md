# ADR 0028 — Autonomy levels without writes before approval; skills as versioned packages that grant no rights

- **Status:** proposed on 2026-10-08; awaits the owner.
- **Packages:** S09 (`agent`, `proactive`).
- **Context documents:** [Leo architecture](../design/leo/ARCHITECTURE.md) §8.5, §9.2; [Leo audit](../design/leo/AUDIT.md) M6, A3; ARCHITECTURE.md fr-4, inv-12.

## Context

In the draft, autonomy is implicit:

- Leo answers and proposes writes.
- Proactivity pushes finished sentences.
- Errands execute approved writes later with no re-check.
- MCP writes execute directly (A3).

Skills are SKILL.md packages from GitHub or skills.sh, pinned to a commit and bound only to role prompt templates. The `agent` role has none, so skills never reach Leo (M6). The brief asks Leo to decide on its own when and what to do, while the user keeps control over critical actions.

## Decision

1. **Autonomy levels:**

   | Level | Leo may | Confirmation |
   |---|---|---|
   | A0 Observe | compute signals and candidates | none |
   | A1 Inform | show a suggestion in its own surfaces | none |
   | A2 Prepare | create Leo-owned artifacts (drafts, briefs, proposed lists) with read-only tools | none |
   | A3 Propose | create an action card | the user approves |
   | A4 Execute | run an approved action | already approved; re-validated if delayed |

   - **No level writes to the user's or company's data, or to an external system, before approval.** Leo's own suggestion store is not the user's data. A draft in the user's mailbox is an external write.
   - **The user's initiative setting caps the level:** `off` = A0, `reserved` = A1–A2 with a low budget, `active` = A1–A3.
2. **Insistence is a separate axis:** `explicit` > `requested` > `initiative` (ADR 0027).
3. **Kill switches:** per user (initiative off), per kind (mute), per policy (platform).
4. **A skill is a versioned package:** instructions, required toolsets, optional output contract, autonomy ceiling, eval suite.
   - **Platform skills** are curated. Their English instructions are registered in the model-facing test. Each has an eval suite.
   - **User skills** (SKILL.md, pinned commit) are untrusted text, wrapped and subordinate to policy. They have no toolsets of their own and an autonomy ceiling of `answer`. At install they are scanned (`noul`: attempts to change the assistant's permissions or safety rules) and refused on a hit.
5. **Activation:** explicit (`/skill`, a UI chip), by `decide(turn.route)`, or bound to a proactive trigger (the morning brief = `daily_brief`).
6. **Standing approvals are not designed.** A confirmation given once for a class of writes would amend inv-12; it is left to the owner (architecture §17 Q-4).

## Alternatives considered

| Option | Why not |
|---|---|
| Configurable autonomy up to unattended writes ("Leo may send routine replies") | contradicts inv-12 as written; needs acceptance data and an explicit amendment first |
| Skills that bring their own tools (code) | executable third-party code in the plane; the draft already refused to run skill scripts; platform tools come only from slices (ADR 0029) |
| Skills as prompt fragments bound to roles (draft) | M6: never reached Leo; no output contract; no evals |
| One fixed behaviour without skills | specialised flows (meeting prep, follow-up, triage) need different toolsets and output shapes; without skills they bloat the base prompt |

## Consequences

- A clear, testable line: anything that changes the user's world passes the Action Gateway (ADR 0025).
- Proactive value comes mostly from A1–A2, which are safe by construction, plus A3 cards the user approves in one tap.
- Skills become the unit of product capability, each with its own eval suite.
- The install scan is a signal, not a guarantee. Wrapping and the policy subordination rule remain the defence.

## Revisit when

- The owner decides Q-4 (standing approvals).
- Acceptance data from phase 7 shows a class of A3 proposals approved more than 95% of the time without edits, a candidate for a standing approval.
