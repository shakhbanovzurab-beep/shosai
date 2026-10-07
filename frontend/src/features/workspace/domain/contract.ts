/**
 * Workspace API contract: the account's workspaces, their people, teams and projects. Shared by the
 * Workspace screens and the route handlers in `../server` (served at `/api/workspaces/*`), which
 * forward to `${BACKEND_API_URL}/v1/workspaces/*` when it is set and otherwise answer from an in-memory
 * demo. snake_case to match Pydantic; errors are `{ "detail": string }`. See docs/workspace-api.md.
 * Meetings, tasks, decisions and knowledge are in `./content-contract.ts`; the account's own view
 * across workspaces (`/api/me/*`) in `./personal-contract.ts`.
 *
 * A workspace the platform's team suspended answers 423 to every call under `/workspaces/{ws}`; it
 * still shows in the list, with `suspended: true`.
 *
 * GET    /workspaces                          → WorkspacesResponse     (every workspace the account is in)
 * POST   /workspaces                          → 201 WorkspaceState     (CreateWorkspaceRequest)
 * GET    /workspaces/{ws}                     → WorkspaceState         (404 when not a member)
 * PATCH  /workspaces/{ws}                     → WorkspaceState         (UpdateWorkspaceRequest; admins)
 * DELETE /workspaces/{ws}                     → 204                    (the owner)
 * POST   /workspaces/{ws}/leave               → 204                    (anyone but the owner)
 * POST   /workspaces/{ws}/invitations         → 201 WorkspaceState     (InviteRequest)
 * DELETE /workspaces/{ws}/invitations/{id}    → WorkspaceState
 * POST   /workspaces/{ws}/invitations/{id}/resend → WorkspaceState
 * PATCH  /workspaces/{ws}/members/{id}        → WorkspaceState         (UpdateMemberRequest)
 * DELETE /workspaces/{ws}/members/{id}        → WorkspaceState
 * POST   /workspaces/{ws}/teams               → 201 WorkspaceState     (TeamInput; admins)
 * PATCH  /workspaces/{ws}/teams/{id}          → WorkspaceState         (TeamInput; admins)
 * DELETE /workspaces/{ws}/teams/{id}          → WorkspaceState         (admins)
 * POST   /workspaces/{ws}/projects            → 201 WorkspaceState     (ProjectInput)
 * PATCH  /workspaces/{ws}/projects/{id}       → WorkspaceState         (Partial<ProjectInput>; lead or admins)
 * DELETE /workspaces/{ws}/projects/{id}       → WorkspaceState         (lead or admins)
 */

/** A workspace as links and lists name it. */
export type WorkspaceRef = { id: string; slug: string; name: string };

/** One owner per workspace; admins run it; members use it. */
export const MEMBER_ROLES = ["owner", "admin", "member"] as const;
export type MemberRole = (typeof MEMBER_ROLES)[number];
/** The roles an invitation or a role change can give: ownership is never handed out that way. */
export type AssignableRole = Exclude<MemberRole, "owner">;
export const ASSIGNABLE_ROLES: readonly AssignableRole[] = ["admin", "member"];

export type WorkspaceSummary = WorkspaceRef & {
  role: MemberRole;
  member_count: number;
  /** Access is paused by the platform's team: nothing in it opens until they restore it. */
  suspended: boolean;
};

export type WorkspacesResponse = { workspaces: WorkspaceSummary[] };

/** A person in one workspace; the same account has a different member id in each workspace. */
export type Member = {
  id: string;
  name: string;
  email: string;
  role: MemberRole;
  /** Job title, e.g. "Designer"; null when not set. */
  title: string | null;
  team_ids: string[];
  joined_at: string;
  /** Null until they first open the workspace. */
  last_active_at: string | null;
};

/** An invitation waiting to be accepted; it holds a seat until then. */
export type Invitation = {
  id: string;
  email: string;
  role: AssignableRole;
  team_ids: string[];
  /** The member who sent it. */
  invited_by: string;
  sent_at: string;
};

/** Team accents use Tailwind's named palette: the theme has no tokens for categorical colours. */
export const TEAM_COLORS = ["blue", "green", "amber", "violet", "rose", "sky"] as const;
export type TeamColor = (typeof TEAM_COLORS)[number];

/** A group of members inside the workspace, e.g. Engineering; meetings and knowledge can be shared with it. */
export type Team = {
  id: string;
  name: string;
  description: string;
  color: TeamColor;
  /** Private teams are seen only by their members and admins, and joined only when added. */
  private: boolean;
  lead_id: string | null;
};

export const PROJECT_STATUSES = ["planned", "active", "paused", "completed"] as const;
export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

/**
 * A piece of work with an outcome, e.g. "Leo beta launch": the shared context its meetings,
 * decisions and tasks belong to. Every member of the workspace can see it.
 */
export type Project = {
  id: string;
  name: string;
  description: string;
  status: ProjectStatus;
  lead_id: string | null;
  /** The team mainly responsible; null when it spans the workspace. */
  team_id: string | null;
  /** A calendar day, "2026-11-16"; null without a target. */
  target_date: string | null;
  created_at: string;
};

/** Where a meeting's notes go once it ends, unless its organizer chooses otherwise. */
export const DEFAULT_SHARE_LEVELS = ["private", "participants", "workspace"] as const;
export type DefaultShareLevel = (typeof DEFAULT_SHARE_LEVELS)[number];

export type SharingPolicy = {
  /** Applies to meetings with workspace members only; meetings with outside guests are never shared on their own. */
  default_level: DefaultShareLevel;
  /** Whether shared meetings include the transcript as well as the summary. */
  share_transcripts: boolean;
  /** Whether members, not only admins, can invite people. */
  members_can_invite: boolean;
};

export type WorkspacePlan = {
  name: string;
  /** Seats paid for; members and pending invitations both take one. */
  seats: number;
  price_per_seat_cents: number;
  currency: string;
  renews_at: string;
};

export type Workspace = WorkspaceRef & {
  /** People with an email at this domain can join without an invitation; null when off. */
  join_domain: string | null;
  sharing: SharingPolicy;
  /** False until an admin confirms the sharing rules; the setup checklist asks for it until then. */
  sharing_reviewed: boolean;
  plan: WorkspacePlan;
  created_at: string;
};

export type WorkspaceState = {
  workspace: Workspace;
  /** The signed-in account's member id in this workspace. */
  me_id: string;
  members: Member[];
  invitations: Invitation[];
  teams: Team[];
  projects: Project[];
};

export const WORKSPACE_NAME_MAX = 60;
export const SEATS_MIN = 2;
export const SEATS_MAX = 100;

export type CreateWorkspaceRequest = { name: string; seats: number };

/** Sending `sharing`, even unchanged, confirms the sharing rules. */
export type UpdateWorkspaceRequest = {
  name?: string;
  join_domain?: string | null;
  sharing?: Partial<SharingPolicy>;
};

export const INVITES_PER_REQUEST = 20;

export type InviteRequest = { emails: string[]; role: AssignableRole; team_ids: string[] };

export type UpdateMemberRequest = { role?: AssignableRole; team_ids?: string[] };

export const TEAM_NAME_MAX = 40;
export const TEAM_DESCRIPTION_MAX = 140;

export type TeamInput = {
  name: string;
  description: string;
  color: TeamColor;
  private: boolean;
  member_ids: string[];
};

export const PROJECT_NAME_MAX = 60;

export type ProjectInput = {
  name: string;
  description: string;
  status: ProjectStatus;
  lead_id: string | null;
  team_id: string | null;
  target_date: string | null;
};
