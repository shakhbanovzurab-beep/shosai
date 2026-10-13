# ADR 0039 — One account per person, with workspaces of the person's home

- **Status:** accepted by the owner on 2026-10-13 (slice map, decision SM-1, narrowed for launch).
- **Packages:** `workspaces`, `identity`, `agent` and every slice with shareable resources (`meetings`, `files`, `knowledge`, `tasks`, `commitments`); M1.
- **Context documents:** [SLICE_MAP.md](../plan/SLICE_MAP.md) §2.8, §8 SM-1, §8.1; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §6, §7, §8.1, §9 inv-15, §10, §19, §22; [Leo architecture](../design/leo/ARCHITECTURE.md) §11.2; [ADR 0038](0038-feature-slices-derived-from-the-product.md).

## Context

- The target architecture (2026-09-30) gave a person with a personal and a work space two accounts: a work account in the company's home, one company per work account, levels owner / selected / organization, no teams.
- The new cabinet shows one account with Personal and several workspaces, a switcher, sharing a personal recording into a workspace, teams, and audiences participants / team / workspace. Two accounts would mean two sign-ins, a switcher that switches accounts, two Leos and no direct share from Personal — more operational load, against the philosophy.
- Residency still holds: a company's data must live in one home (152-FZ, GDPR), and the legal review of cross-border data (§22) is not done.

## Decision

1. **One account per person**, in the home chosen by their country at registration. Personal and every workspace the person belongs to are spaces of that account.
2. **A workspace has one home**, fixed at creation: the home of the person who creates it, or the home a company contract names. All of its data lives there (inv-15). Membership rows live in the workspace's home and reference the person's global user id.
3. **At launch a person joins only workspaces of their own home.** An invitation or a domain join across homes is refused with an explicit error (409 on join). Cross-home membership, the profile copy it needs in the workspace's home and cross-home sharing wait for the legal review (§22); the data model leaves room for them.
4. **Access levels stay** `owner | selected | organization`. A grantee in `resource_grants` is a member or a team. The cabinet's audiences map onto the levels: participants → `selected`, team → `selected` with the team as grantee, workspace → `organization`. Guest stays in the model without a screen.
5. **Sharing a personal item** into a workspace is a share record owned by `workspaces`; the item is not copied, because both live in the same home. Removing the share or leaving the workspace ends the workspace's access.
6. **The token carries no workspace roles.** Membership is checked in every reading query and never cached (§7), so removing a member ends their access to that workspace at the next request without signing them out of Personal.
7. **Leo is one per person.** It reads everything the person may access, in Personal and in every workspace they belong to; every read passes the access policy; every answer names its sources and the space each comes from; losing membership removes that workspace from Leo at once. A thread's scope (personal, workspace, hub) ranks its own space first and is the default target of writes; a write into another space names that space in its preview.

## Consequences

- ARCHITECTURE §6–§7, §8.1 (Workspace, Membership, Access), inv-15, §10 (invite and join), §19 and §22 are amended; the Leo architecture's §11.2 scope rule is amended from "a scope limits every read" to "a scope focuses, the access policy limits".
- A person in a workspace sees it in the same session as Personal: one sign-in on web and desktop, one Leo, one search over every space they may access.
- A workspace request runs in the person's own home at launch, so no workspace-home lookup sits on the request path yet.
- `PrincipalFactory` carries the person's active memberships, read per run; a membership change takes effect on the next run.
- An account transfer between homes of a person who belongs to workspaces has no rule yet: it is listed in §22 and settled in the `workspaces` plan before transfers of members are allowed.
- The draft has no companies (DATA_MAPPING fact 2), so M1 migrates nothing for workspaces.

## Revisit when

- The legal review allows cross-home membership → a workspace request resolves the workspace's home from an org directory (cached like the user directory), memberships of another home get a profile copy, and cross-home sharing copies the item after the owner confirms.
- A company customer needs members in both homes before the review ends → that customer's workspace is placed by contract and its members of the other home are refused until the review.
- Users need a fully separate work identity (for example a company that requires its own sign-in) → enterprise sign-in (fr-17) adds a per-workspace identity provider, not a second account model.
