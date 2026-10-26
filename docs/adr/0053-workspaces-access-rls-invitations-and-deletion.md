# ADR 0053 — Workspaces: RLS across a person's workspaces, invitations, member deletion and workspace deletion

- **Status:** accepted by the owner on 2026-10-17 (workspaces slice plan, decisions WS-D1 … WS-D7; the Leo scope question settled by ADR 0039).
- **Packages:** `workspaces`; core (`core/db`: the company and personal policies, the sweep role); `identity` (deletion and transfer of a member); every slice with shareable resources or rows with `org_id`; `billing` (seats); `agent` (scope); F4 runbook (the sweep role on staging and production).
- **Context documents:** [workspaces plan](../plan/slices/workspaces.md); [ARCHITECTURE.md](../design/ARCHITECTURE.md) fr-12 … fr-14, nfr-14 … nfr-17, §6, §7, §8.1, §9 inv-14 … inv-17, §10, §16.4, §22; [F1 audit](../plan/audits/F1-audit.md) A2, OD-5; F1 plan F1-C6; [ADR 0039](0039-one-account-per-person-with-workspaces.md); [ADR 0045](0045-identity-sessions-registration-and-deletion.md).

## Context

- One account per person reads Personal and every workspace the person belongs to (ADR 0039). Core's row-level security showed a transaction only the one company of `app.org_id`, so a read across spaces needed one transaction per space: 4 round trips of 45 ms each for a Russian user.
- The F1 audit left RLS for personal rows (OD-5) and the role for cross-tenant sweeps (F1-C6) to this slice.
- The cabinet has email invitations only and no screen to accept one or to verify a domain. fr-12 names links, email and a verified domain.
- Nothing said what happens to a workspace whose last owner deletes their account, how a member's account moves between homes, or how a workspace is deleted and exported (fr-14).
- Billing sells seats only in wave 3, while the access policy is needed in wave 1.
- The cabinet's `workspace-api.md` said Leo in a workspace answers only from that workspace and never from personal files, which contradicts ADR 0039.

## Decision

1. **RLS across a person's workspaces (WS-D1).**
   - Reads: the company policy shows a row when `org_id IS NULL`, or it is the company of the scope, or it is a company the person is an active member of.
   - The membership set comes from `app_member_org_ids()`, a `SECURITY DEFINER` function that is evaluated once per statement and never cached.
   - Writes: `WITH CHECK` admits only the company of the scope.
   - The access policy, not RLS, narrows a row to its access level.
2. **Personal rows and sweeps (WS-D2).**
   - Tables that are personal by nature and never shared get `user_isolation` (`user_id = app_user_id()`).
   - Shareable tables get the company policy only; their personal rows are guarded by the access policy and the isolation tests.
   - identity's account tables keep no RLS, because they are read before a principal exists.
   - Cross-tenant sweeps run as the `NOLOGIN` role `shosai_sweeper`:
     - the application role may `SET ROLE` to it (`WITH INHERIT FALSE, SET TRUE`);
     - its policies are `TO shosai_sweeper USING (true)`;
     - `HomeTransactions.begin(scope, sweep=True)` sets it inside the transaction, with one pool;
     - it is allowed only in the `workers` and `scheduler` roles, and read-only in the `agent` engineer command: a one-shot command on the host that serves no request and lists Leo's donated evaluation cases, each read of a case audited (ADR 0068 AG-D13; **amended by the owner on 2026-10-26**).
3. **Invitations and domain join (WS-D3).**
   - Invitations are by email only. Each one is a one-time link: 32 bytes, SHA-256 stored, 14 days, rotated on resend, bound to the invited address and to the workspace's home.
   - There is no reusable link at launch.
   - A domain is verified by a DNS TXT record; public mail domains are refused; `directory_domains` in the EU home gives a domain to one workspace across both homes.
   - A person with a verified email at that domain joins with one click, never silently.
4. **A member's account (WS-D4).**
   - While identity hides an account, its memberships are hidden: they hold their seats, the person's shares are not served, and a cancellation restores them.
   - At erasure the membership is removed. Ownership of a workspace whose only owner was erased passes to the longest-standing admin, else to the longest-standing member.
   - A workspace with no other member is deleted with the account.
   - An account transfer is refused while the person has memberships.
5. **Deleting a workspace (WS-D5).**
   - The owner's delete hides the workspace at once.
   - The owner or the platform admin can cancel within 7 days.
   - Then a saga erases every slice's company rows and objects through the workspace-data registry. Personal recordings and files stay with their owners.
   - The owner can export the workspace's data as one ZIP.
6. **Company consent (WS-D6).** At launch an AI call on workspace data uses the acting person's consent. `operator_consent_at` stays empty until the first company contract (§22).
7. **Seats before billing (WS-D7).**
   - Until billing's payments ship, workspaces exist only in tests and other slices' fixtures; no route creates one.
   - The seat check is a required port bound by billing. While it is unbound, every join and invitation is refused (inv-3).
8. **Leo's scope (ADR 0039, confirmed).**
   - The space of a conversation sets Leo's focus; the access policy sets its bounds.
   - In a workspace Leo looks there first and writes there by default, and it may use anything else the person may open, Personal included.
   - Every answer names its sources and the space each comes from.
   - Leo never reads or counts what the person cannot open.
   - The cabinet's `workspace-api.md` is corrected.

## Consequences

- Core's `enable_company_isolation` is replaced. Its existing tables migrate to the new policy in workspaces step 2.
- `deploy/local/postgres/init-home.sh` and the staging and production setup create `shosai_sweeper` in each home. A managed PostgreSQL that refuses `SET ROLE` is found in step 2, before any slice depends on it.
- ARCHITECTURE is amended:
  - §2 nfr-16: a removed member loses the workspace at the next request; their sessions and Personal stay;
  - §7: the policies, the sweep role, invitations and domain join;
  - §8.1: workspace retention;
  - §10: invite and join; share through each share record's own route;
  - §16.4: the inv-16 monitor;
  - §22: the transfer of a member.
- Two new cabinet screens: accept an invitation, and the domain's verification state. Settings gains the workspace export.
- The cabinet's Leo mock (`features/leo/mocks/knowledge.ts`) still limits a workspace conversation to that workspace and counts items the person cannot open. It is deleted when `agent` serves Leo; the agent plan follows this ADR, not the mock.

## Revisit when

- RLS overhead exceeds 10% of query time on a meeting read or search (§19) → reconsider the membership subquery.
- The legal review allows cross-home membership (§22) → memberships of another home, a workspace-home lookup per request, a transfer rule for members.
- A company asks for "anyone with the link can join" → a reusable invitation link with an expiry and a seat cap.
- The first company contract is signed → `operator_consent_at` and its effect on `CallContext`.
