# ADR 0067 — An event's delivery runs in the scope its consumer names from the event

- **Status:** proposed on 2026-10-23 by the agent building tasks' step 6, under the owner's instruction of 2026-10-23 to carry the tasks slice through on its own and decide unusual points by industry practice; for the owner's review. Extends §12's subscriptions; changes no event and no contract of a slice.
- **Packages:** `core.events` (`EventSubscription.scope`, the delivery), `features.tasks` (its consumers of workspaces' events).
- **Context documents:** target architecture §7 (row-level security), §12; [tasks plan](../plan/slices/tasks.md) step 6; [ADR 0005](0005-data-without-owner-in-eu-home.md).

## Context

A delivery ran in the event's own scope: the person and company of the producer's transaction. Tasks' step 6 follows `workspaces.member.removed` — the departed member's tasks of the workspace are unassigned or passed to the successor, and their own places of those tasks on their boards go. Those are the workspace's rows and the departed person's own rows, while the event's scope is whoever ended the membership; when an account's erasure ends it, the scope need not name the workspace at all, and row-level security then hides the rows, so an `UPDATE` silently matches none. The plan named the sweep role for the placements, but that role is read-only everywhere: sweeps find rows across tenants and the writes happen in each tenant's scope. Granting it writes for one delivery would make a role that bypasses isolation a writer.

## Decision

`EventSubscription` gains `scope`: a function of the event and its scope that names the person and company the effect writes as, in the event's home (moving the effect to another home stays `home`'s job, and a scope in another home is refused). The delivery opens its one transaction in that scope, so the effect and the delivery mark still commit together and a redelivery changes nothing. Tasks' `tasks.follow_departure` runs as the departed person in the workspace they left, and `tasks.forget_project` in the workspace whose project went; row-level security admits exactly those rows. A consumer without `scope` keeps the event's.

## Consequences

- The sweep role stays read-only; no grant changes.
- The effect is applied exactly once with its mark, as every delivery is; a lifecycle consumer guards against a late delivery itself (tasks leaves a member who is active again as they are).
- A consumer acting as a person other than the event's is a choice visible in its declaration and reviewed like any write path; it names its rows explicitly.
