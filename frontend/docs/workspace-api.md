# Workspace API

The contract between the Workspace pages (`/app/w/{slug}/*`), the parts of Personal that show
workspace work, and the FastAPI backend. The TypeScript types are the source of truth (snake_case):
`src/features/workspace/domain/contract.ts` (workspaces, people, teams, projects),
`content-contract.ts` (meetings, decisions, tasks, usage), `knowledge-contract.ts` (files and
sources) and `personal-contract.ts` (the account's view across workspaces). The browser calls `/api/workspaces/*` and `/api/me/*`, which forward
to `${BACKEND_API_URL}/v1/…` when set and otherwise answer from an in-memory demo
(`src/features/workspace/server/`). Errors: `{"detail": "message"}`.

## Model

```
Account
├── Personal          mail, calendar, notes (recordings), boards, files (File Manager): owned by the account
└── Workspaces        one or more, each billed per seat on the Team plan
    ├── Members       owner · admin · member (one member id per workspace for the same account)
    ├── Teams         optional groups; private ones are seen only by their members and admins
    ├── Projects      the shared context of a piece of work: its meetings, tasks and decisions
    └── Shared work   meetings, decisions, tasks, knowledge (files and connected sources)
```

**Nothing is copied between Personal and a workspace.** Three kinds of links connect them:

| Personal object | In a workspace it is… | Ownership |
| --- | --- | --- |
| A recording in Notes | a shared meeting with the same id, in at most one workspace at a time, with an audience: `participants`, a `team`, or the `workspace` | stays the recorder's; stopping sharing takes it out, leaving or being removed withdraws it |
| A file in File Manager | a knowledge item whose `source` is `{kind: "personal", file_id}`, for a team or everyone, optionally in a project; can be shared in several workspaces | stays the owner's; stopping sharing or deleting it removes it; the owner can transfer it, and it becomes the workspace's (`{kind: "upload"}`) |
| *(the account)* | tasks assigned to its member: shown in Personal Productivity and, opt-in, on one Kanban board | tasks are the workspace's; changing them from Personal changes the workspace's task |

A seat in a workspace on the Team plan also covers the member's own tools: the Upgrade API reports it
as `seat` / `effective_plan_id` (see docs/upgrade-api.md).

**Knowledge** is what Leo knows in a workspace: the meetings, decisions and projects each member can
open (always, nobody adds them), plus knowledge items of three kinds, which decide who owns them:

| `source.kind` | What it is | Owner | When its adder leaves |
| --- | --- | --- | --- |
| `upload` | a file uploaded to the workspace, or transferred to it | the workspace | stays |
| `personal` | a member's own file, shared from File Manager | the member | leaves with them |
| `connector` | a source the workspace connected (`drive`, `notion`, `confluence`, `web`) | the workspace | stays |

There is no workspace file manager: files show in Knowledge, and on their project's page when they
have a `project_id`.

## Endpoints

All workspace paths are under `/workspaces/{ws}` (the workspace id; pages use the slug). Every one of
them answers `404` when the workspace doesn't exist **or** the account isn't a member, and `423` while
the platform's team has the workspace suspended (see `admin-workspaces-api.md`). A suspended workspace
still appears in `GET /workspaces` with `suspended: true`; `/me/*` leaves it out.

| Method   | Path                              | Body                                                   | Response              | Who |
| -------- | --------------------------------- | ------------------------------------------------------ | --------------------- | --- |
| `GET`    | `/workspaces`                     | —                                                      | `{workspaces}` (each with `role`, `member_count`, `suspended`) | the account |
| `POST`   | `/workspaces`                     | `{name, seats}`                                        | `201 WorkspaceState`  | the account (becomes owner) |
| `GET`    | `/workspaces/{ws}`                | —                                                      | `WorkspaceState`      | members |
| `PATCH`  | `/workspaces/{ws}`                | `{name?, join_domain?, sharing?}`                      | `WorkspaceState`      | admins |
| `DELETE` | `/workspaces/{ws}`                | —                                                      | `204`                 | owner |
| `POST`   | `/workspaces/{ws}/leave`          | —                                                      | `204`                 | anyone but the owner (`409`) |
| `POST`   | `…/invitations`                   | `{emails, role, team_ids}`                             | `201 WorkspaceState`  | admins, or members when `members_can_invite` |
| `DELETE` | `…/invitations/{id}`              | —                                                      | `WorkspaceState`      | admins or the inviter |
| `POST`   | `…/invitations/{id}/resend`       | —                                                      | `WorkspaceState`      | admins or the inviter |
| `PATCH`  | `…/members/{id}`                  | `{role?, team_ids?}`                                   | `WorkspaceState`      | admins; anyone for their own open teams |
| `DELETE` | `…/members/{id}`                  | —                                                      | `WorkspaceState`      | admins, never the owner |
| `POST`   | `…/teams` · `PATCH`/`DELETE` `…/teams/{id}` | `{name, description, color, private, member_ids}` | `WorkspaceState` | admins |
| `POST`   | `…/projects`                      | `{name, description, status, lead_id, team_id, target_date}` | `201 WorkspaceState` (new project first) | members |
| `PATCH`  | `…/projects/{id}`                 | any of the above                                       | `WorkspaceState`      | lead or admins |
| `DELETE` | `…/projects/{id}`                 | —                                                      | `WorkspaceState`      | lead or admins |
| `GET`    | `…/meetings`                      | —                                                      | `{meetings, upcoming}`| members |
| `POST`   | `…/meetings`                      | `{recording_id, visibility, project_id, transcript_shared}` | `201 TeamMeetingDetail` | the recording's owner (moves it here if shared elsewhere) |
| `GET`    | `…/meetings/{id}`                 | —                                                      | `TeamMeetingDetail`   | who can see it |
| `PATCH`  | `…/meetings/{id}`                 | `{visibility?, transcript_shared?, project_id?}`       | `TeamMeetingDetail`   | organizer or admins |
| `DELETE` | `…/meetings/{id}`                 | —                                                      | `204`                 | organizer (stop sharing) or admins (remove) |
| `GET`    | `…/decisions`                     | —                                                      | `{decisions}`         | members |
| `GET`    | `…/tasks` · `POST` `…/tasks`      | `{title, assignee_id, due_on, project_id}`             | `{tasks}` · `201 Task`| members |
| `PATCH`  | `…/tasks/{id}`                    | `{title?, status?, assignee_id?, due_on?, project_id?}`| `Task`                | who can see it |
| `GET`    | `…/knowledge`                     | —                                                      | `{items}`             | members |
| `POST`   | `…/knowledge`                     | multipart: `files`, `level`, `team_id`, `project_id`   | `201 {items}`         | members (uploads belong to the workspace) |
| `POST`   | `…/knowledge/publish`             | `{file_id, name, size_bytes, content_type, access, project_id}` | `201 KnowledgeItem` (or the existing one, re-scoped) | the file's owner |
| `POST`   | `…/knowledge/sources`             | `{provider, name, url, access}`                        | `201 KnowledgeItem`   | admins |
| `PATCH`  | `…/knowledge/{id}`                | `{access?, project_id?}`                               | `KnowledgeItem`       | who added it, or admins |
| `DELETE` | `…/knowledge/{id}`                | —                                                      | `204` (removes an upload or source; stops sharing a file) | who added it, or admins |
| `GET`    | `…/usage`                         | —                                                      | `{month_start, members}` | admins |
| `GET`    | `/me/tasks`                       | —                                                      | `{tasks}` (`MyTask`: + `workspace`, `project_name`) | the account |
| `GET`    | `/me/meetings`                    | —                                                      | `{workspaces: [{workspace, meetings}]}` (shared with the account, not its own) | the account |
| `GET`    | `/me/shares`                      | —                                                      | `{recordings, files}` (where the account's things are shared, with live tasks) | the account |
| `GET`    | `/me/knowledge`                   | —                                                      | `{workspaces: [{workspace, items, meetings, decisions, projects}]}` (what Leo may use for the account in Personal) | the account |

## Access rules the backend enforces

- **Meetings**: the organizer always sees a meeting; members who took part see it at any level; a
  `team` audience adds that team's members; `workspace` is everyone. Admins can change who sees a
  meeting they can see, but don't see meetings they couldn't otherwise.
- **Transcripts**: people a meeting is shared with get `transcript: null` unless `transcript_shared`.
- **Sharing rules**: `sharing.default_level` applies to meetings where everyone is a member; a meeting
  with anyone from outside the workspace is never shared on its own (`UpcomingMeeting.shares_with` is
  null). Sending `sharing`, even unchanged, sets `sharing_reviewed`.
- **Tasks**: visible to whoever can see their meeting; tasks added by hand (no meeting) to everyone; a
  task's assignee always. When its meeting stops being shared, a task stays, visible to its assignee and
  admins only, so the meeting's audience never widens.
- **Knowledge for Leo**: in a workspace, Leo answers only from that workspace: the meetings,
  decisions and projects the member can open, and items the member may use as a member (for
  everyone, their teams, or added by them). Admin rights don't widen it. The check runs before
  anything reaches the model; the answer says how many items it left out. In Personal, Leo also
  uses what every workspace lets the member use (`GET /me/knowledge`), labeled by workspace, and only
  for them; it never brings personal files into a workspace answer.
- **Connected sources** belong to the workspace; disconnecting stops syncing and removes their
  vectors. Nothing changes at the provider.
- **Seats**: invitations are refused with `409` beyond the seats left; pending invitations hold a seat.
- **Leaving / removal**: the person's shared recordings and files are withdrawn; files they
  transferred, their uploads and sources stay; tasks stay, open ones become unassigned; teams and
  projects they led lose their lead.
- **Deleting a team** narrows its meetings to their participants and is refused (`409`) while any knowledge
  is shared with that team. **Deleting a project** keeps its meetings, tasks and files.
- **Event log**: invitations, role changes, removals, departures, settings changes and file
  transfers are recorded for the platform's team (the admin panel shows them with its own actions).
- **Deleting a workspace** removes its projects, tasks, decisions, uploads and sources; recordings
  and shared files stay in their owners' Notes and File Manager.
