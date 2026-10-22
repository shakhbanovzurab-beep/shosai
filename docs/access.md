# Access for a slice

How a slice lets people share its rows: meetings, notes, folders, files, knowledge items. The rules are §7 of the [target architecture](design/ARCHITECTURE.md#7-tenancy-and-access-control), [ADR 0039](adr/0039-one-account-per-person-with-workspaces.md) and [ADR 0053](adr/0053-workspaces-access-rls-invitations-and-deletion.md). One access policy decides every read and write; a slice never compares owners itself.

## 1. The table

A shareable table carries the row's personal owner, its workspace and its access level:

```python
user_id: Mapped[UUID]                       # the person who owns the row
org_id: Mapped[UUID | None]                 # its workspace; empty for a personal row
access: Mapped[str | None]                  # owner | selected | organization; empty when personal
```

- A check keeps `org_id` and `access` empty together or set together.
- Indexes on `org_id` and on `user_id`: the policy's pre-filters reach rows through them.
- Declare it on the slice's `FeatureModule`: `shareable=(ShareableResource("meeting", Meeting.__table__),)` (`core/access/shareable.py`). Column names other than these defaults are named in the declaration. One kind and one table per declaration across slices.
- **A parent and a named reader** ([ADR 0059](adr/0059-tasks-one-store-boards-action-items-and-jira.md)). A workspace's row may also open to whoever may read its parent row now, and to the active member a column names: `ShareableResource("task", tasks, parent=("meeting", "source_meeting_id"), reader="assignee_user_id")`. The parent is another declared kind, found by the policy among every slice's declarations, and has no parent of its own (composition refuses a chain or an undeclared kind). Both rules widen reading inside the row's workspace only — the reader must be an active member there, and a parent read through another workspace opens nothing — and neither lets anyone manage the row's access. The parent's predicate runs in an `EXISTS` of the same query, so the right is never copied.

## 2. The migration

```python
enable_company_isolation("meetings")           # RLS: rows of the person's workspaces
grant_to_application(scope, "meetings")
grant_to_sweeper("meetings", ("SELECT",))      # the inv-14 self-test reads it as the sweep role
```

- The company policy calls `app_member_org_ids()`, created by workspaces' revision `c41d7e9a2b85`: the slice's revision comes after it.
- A table that is personal by nature and never shared takes `enable_user_isolation` instead (Leo threads, memory facts, hubs).
- Sweeps over every tenant run in a workers or scheduler process with `transactions.begin(scope, sweep=True)`; the sweep role sees only what migrations grant it.

## 3. Reading

The predicate goes into the slice's own query, so the check runs with the read and nothing is cached:

```python
policy = services.ports.get(ACCESS_POLICY)          # workspaces.contracts
viewer = Viewer(principal.user_id)                  # Leo, Personal, search
viewer = Viewer(principal.user_id, within=org_id)   # a workspace screen
query = select(Meeting).where(policy.readable(MEETINGS, viewer))
```

- `within` narrows a workspace screen to that workspace; it is not a boundary, and Leo never sets it (ADR 0053 point 8).
- A transaction for the person: `TenancyScope(home, user_id)`; a write into a workspace: `TenancyScope(home, user_id, org_id)`. Row-level security writes a workspace's rows only in its scope.
- A missing row and a row the person may not read answer the same 404.
- Search hits and Leo's sources pass `policy.filter_readable(session, MEETINGS, ids, viewer)` before they leave the slice: the index lags access changes by seconds.

## 4. Changing access

`policy.manageable(resource, viewer)` says who may change a row's access: its owner, and the workspace's admins for rows they can read. The change itself is one call in the workspace's transaction:

```python
await policy.set_access(session, AccessChange(MEETINGS, meeting_id, org_id, level, grantees, Viewer(user_id)))
```

It checks the actor and the grantees, replaces the grants, writes the audit row and publishes `workspaces.access.changed`. A personal row shared into a workspace is changed through its share record (workspaces' routes), not here.

## 5. The isolation test

Every read path of the resource is checked against the rules with the kit (§14 rule 12):

```python
@pytest.mark.isolation(resource="meeting")
async def test_the_meeting_list_obeys_the_access_rules(homes, run_slot) -> None:
    async def path(viewer: Viewer) -> set[UUID]:
        ...  # call the slice's read path for the viewer, return the ids it shows
    await assert_isolated(run_slot.claimed.connections[Home.RU], MEETINGS, path)
```

- `tests/support/isolation.py` writes the canonical world (`tests/support/isolation_world.py`) — two workspaces, a member of both, a guest, a private team, a removed member, a hidden owner, personal rows shared and not — and names any row a person sees or misses against `tests/support/access_model.py`. A resource with a named reader gets rows naming each kind of person; a resource with a parent gets the parent kind's world, written to the parent's table through `parents={"meeting": (MEETING_RESOURCE, columns)}`, a child under each parent, a child in the other workspace and one whose parent is gone. `extra` may be a function of the row, for columns that depend on it.
- `tests/architecture/test_isolation_gate.py` fails while a declared kind has no marked test under `tests/features/<slice>/`.

## 6. Events to follow

| Event | What the slice does |
|---|---|
| `workspaces.member.removed` | rows of that workspace owned by `user_id` get `successor_user_id` as owner (nfr-16) |
| `workspaces.access.changed` | refresh the row's payload in derived stores (Qdrant) |
| `workspaces.project.deleted` | clear `project_id` on its rows |
| `workspaces.workspace.deleted` | nothing to read any more; erasure itself runs through the workspace-data registry (workspaces step 11) |

Monitoring of the policy is workspaces' own: the hourly self-test pages on `PolicyDisagreesWithRls` ([runbook](runbooks/alerts.md#policy-disagrees-with-rls)).
