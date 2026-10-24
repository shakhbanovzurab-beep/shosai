# workspaces

A company's shared space inside each person's one account: members, roles, teams, projects, invitations, sharing defaults and the share records that bring a member's meeting or file into a workspace. It owns the **one access policy** every slice with shareable resources calls, the row-level security behind it and the workspace audit log.

- Plan: [docs/plan/slices/workspaces.md](../../../../../docs/plan/slices/workspaces.md).
- Decisions: [ADR 0039](../../../../../docs/adr/0039-one-account-per-person-with-workspaces.md) (one account, workspaces of the person's home, one Leo), [ADR 0053](../../../../../docs/adr/0053-workspaces-access-rls-invitations-and-deletion.md) (RLS across a person's workspaces, invitations, member and workspace deletion, seats before billing).

## Public surface

Other slices import only `contracts` (the package) and `contracts.events`:

| Item | What it is |
|---|---|
| `AccessPolicy` (`ACCESS_POLICY`) | The predicate a slice puts into its own query (`readable`, `manageable`), the batch re-check of search hits (`filter_readable`), the workspace a member reads someone else's shared personal row through — the space Leo names that source by (`shared_into`, agent step 6) — and the one way to change access (`set_access`) |
| `Viewer` | The person reading; `within` narrows a workspace screen, never Leo |
| `ShareableResource` (core) | Declared on a slice's `FeatureModule.shareable` for each table it shares, naming its id, owner, workspace and access columns |
| `MembershipReader` (`MEMBERSHIP_READER`) | A person's active memberships, read in the caller's transaction; the account transfer guard |
| `AuditLog` (`AUDIT_LOG`) | One audit row in the caller's transaction |
| `SeatAllowance` (`SEAT_ALLOWANCE`) | Billing's seats; until billing binds it, every join is refused |
| `KnowledgeTransfer` (`KNOWLEDGE_TRANSFER`) | files' transfer route: the member's shared item becomes the workspace's upload with its level, its grants move under the file, the file's items elsewhere are withdrawn, one `file_transferred` audit row (step 9a) |
| `contracts.events` | `workspaces.workspace.*`, `.member.*`, `.team.deleted`, `.project.deleted`, `.access.changed`, `.meeting.*`, `.knowledge_item.*` |

## Rules the domain holds

- `domain/roles.py` — the permission matrix of the cabinet's `roles.ts`: owner-only billing, deletion and export; admins manage people, teams, settings, sources and usage; members invite when the workspace allows it; only admins invite admins; nobody manages the owner or themselves; a member joins only open teams.
- `domain/memberships.py` — `active`, `hidden` (the account's deletion window), `removed`; a workspace always keeps a standing owner; the successor of an erased only owner is the longest-standing admin, else member.
- `domain/access.py` — levels `owner | selected | organization`, member and team grants, the cabinet's audiences, and `level_admits`, the reference decision the SQL predicate must agree with.
- `domain/seats.py`, `slugs.py`, `invitations.py`, `domains.py`, `audit.py` — seats held by members and pending invitations; immutable slugs in every script; one-time invitation tokens stored as SHA-256; company domains without public mail services; the closed set of audit actions.

## Monitors and guide

- inv-14: the hourly self-test pages on `PolicyDisagreesWithRls` when the policy would open a workspace row outside a person's workspaces; inv-16: the daily check pages on `WorkspaceOverSeats` ([runbook](../../../../../docs/runbooks/alerts.md#policy-disagrees-with-rls)).
- Slices with shareable resources follow [docs/access.md](../../../../../docs/access.md).
- `files.file.deleted` (consumer `workspaces.withdraw_deleted_file`, `channels/file_consumers.py`) takes a deleted personal file out of every workspace it was shared in, with its grants and one `knowledge_item.removed` each.
