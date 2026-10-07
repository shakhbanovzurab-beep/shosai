/**
 * Admin › Пространства: every workspace on the platform, for the team running it. The route
 * handlers in `server/` (mounted under `src/app/api/admin/workspaces`) forward to
 * `${BACKEND_API_URL}/v1/admin/workspaces/*` and fall back to the workspace demo. snake_case; errors
 * are `{ "detail": string }`. See docs/admin-workspaces-api.md.
 *
 * Metadata and counts only: the platform's team never sees meeting notes, files or tasks themselves.
 *
 * GET    /admin/workspaces               → AdminWorkspacesResponse
 * GET    /admin/workspaces/{id}          → AdminWorkspaceDetail
 * PATCH  /admin/workspaces/{id}          → AdminWorkspaceDetail   (SeatsRequest)
 * DELETE /admin/workspaces/{id}          → 204
 * POST   /admin/workspaces/{id}/suspend  → AdminWorkspaceDetail   (SuspendRequest)
 * POST   /admin/workspaces/{id}/resume   → AdminWorkspaceDetail
 * POST   /admin/workspaces/{id}/owner    → AdminWorkspaceDetail   (OwnerRequest)
 */

/** Suspended wins over the billing standing: nobody can use the workspace until it is resumed. */
export const WORKSPACE_STATUSES = ["active", "trialing", "past_due", "suspended"] as const;
export type WorkspaceStatus = (typeof WORKSPACE_STATUSES)[number];

export type MemberRole = "owner" | "admin" | "member";

export type AdminPlan = {
  name: string;
  seats: number;
  price_per_seat_cents: number;
  currency: string;
  renews_at: string;
};

export type AdminWorkspace = {
  id: string;
  name: string;
  slug: string;
  owner: { name: string; email: string } | null;
  plan: AdminPlan;
  status: WorkspaceStatus;
  /** Set while the workspace is on a trial. */
  trial_ends_at: string | null;
  members: number;
  pending_invitations: number;
  /** Members plus pending invitations. */
  seats_used: number;
  /** Seats × price per seat. */
  monthly_cents: number;
  meetings_month: number;
  minutes_month: number;
  /** The latest any member was active; null when nobody has opened it yet. */
  last_active_at: string | null;
  created_at: string;
};

export type AdminWorkspacesResponse = { workspaces: AdminWorkspace[] };

export type AdminMember = {
  id: string;
  name: string;
  email: string;
  role: MemberRole;
  teams: number;
  meetings_month: number;
  minutes_month: number;
  joined_at: string;
  last_active_at: string | null;
};

export const EVENT_ACTIONS = [
  "workspace_created",
  "member_invited",
  "invitation_revoked",
  "role_changed",
  "member_removed",
  "member_left",
  "settings_changed",
  "file_transferred",
  "seats_changed",
  "owner_transferred",
  "suspended",
  "resumed",
] as const;
export type EventAction = (typeof EVENT_ACTIONS)[number];

export type AdminEvent = {
  id: string;
  at: string;
  action: EventAction;
  /** A member's name, or null when the platform's team did it. */
  actor: string | null;
  target: string | null;
  value: string | null;
};

export type AdminWorkspaceDetail = AdminWorkspace & {
  join_domain: string | null;
  sharing: {
    default_level: "private" | "participants" | "workspace";
    share_transcripts: boolean;
    members_can_invite: boolean;
  };
  suspension: { at: string; reason: string } | null;
  people: AdminMember[];
  invitations: { email: string; role: MemberRole; sent_at: string }[];
  teams: { id: string; name: string; members: number; private: boolean }[];
  /** Counts only; what they contain stays private to the workspace. */
  content: {
    shared_meetings: number;
    decisions: number;
    open_tasks: number;
    projects: number;
    active_projects: number;
    files: number;
    sources: number;
    knowledge_bytes: number;
  };
  /** Newest first. */
  events: AdminEvent[];
};

export type SeatsRequest = { seats: number };
export type SuspendRequest = { reason: string };
export type OwnerRequest = { member_id: string };

export const SUSPEND_REASON_MAX = 300;
export const SEATS_LIMIT = 500;
