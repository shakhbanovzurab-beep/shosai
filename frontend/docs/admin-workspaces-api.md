# Admin workspaces API

The contract between Admin › Пространства (`/admin/workspaces`, `/admin/workspaces/{id}`) and the
FastAPI backend. The TypeScript types in `src/features/admin-workspaces/domain/contract.ts` are the
source of truth (snake_case). The browser calls `/api/admin/workspaces/*`, which forwards to
`${BACKEND_API_URL}/v1/admin/workspaces/*` when set and otherwise answers from the workspace demo
(`src/features/workspace/server/control.ts`). Errors: `{"detail": "message"}`, in Russian: only the
admin panel shows them.

## What the platform's team sees

Every workspace on the platform, with **metadata and counts only**: who owns it, its plan and seats,
what it pays, how much it is used, its access rules, its teams, and its event log. Meeting notes,
transcripts, file contents and task titles never reach this API; `content` carries counts.

`status` is `suspended` while access is paused, otherwise the billing standing: `active`,
`trialing` (with `trial_ends_at`) or `past_due`.

## Endpoints

| Method   | Path                              | Body             | Response                 |
| -------- | --------------------------------- | ---------------- | ------------------------ |
| `GET`    | `/admin/workspaces`               | —                | `AdminWorkspacesResponse` |
| `GET`    | `/admin/workspaces/{id}`          | —                | `AdminWorkspaceDetail`   |
| `PATCH`  | `/admin/workspaces/{id}`          | `{seats}`        | `AdminWorkspaceDetail`   |
| `DELETE` | `/admin/workspaces/{id}`          | —                | `204`                    |
| `POST`   | `/admin/workspaces/{id}/suspend`  | `{reason}`       | `AdminWorkspaceDetail`   |
| `POST`   | `/admin/workspaces/{id}/resume`   | —                | `AdminWorkspaceDetail`   |
| `POST`   | `/admin/workspaces/{id}/owner`    | `{member_id}`    | `AdminWorkspaceDetail`   |

## Rules the backend enforces

- **Seats** are never fewer than members plus pending invitations (`409`), and at most 500 (`422`).
  The new total is billed from the next charge.
- **Suspending** needs a reason (3–300 characters), kept in the event log for other admins. Every
  call under `/workspaces/{ws}` then answers `423` for the workspace's members, the workspace shows
  `suspended: true` in their list, and their Personal views (`/me/*`, Kanban, Leo) leave it out.
  Nothing is deleted and billing continues. `resume` restores it as it was.
- **Ownership** goes to an existing member; the previous owner becomes an admin. For when the owner
  left the company or can't be reached.
- **Deleting** works as the owner's delete: projects, tasks, decisions, uploads and sources go;
  shared recordings and files stay with the people who own them.
- **Event log** (`events`, newest first): the workspace's own changes (created, invitations sent and
  revoked, role changes, members removed or leaving, settings changed, files transferred) and every
  platform action (seats, ownership, suspension, resumption). `actor` is the member's name, or
  `null` for the platform's team; `target` and `value` carry what changed (a name, an email, a
  role, "10 → 12", the settings keys).

The list's summary (workspaces, seats, monthly revenue without suspended ones, meeting minutes this
month, and how many need attention: suspended, past due, out of seats, or nobody active for 14
days) is computed in the browser from the list.
