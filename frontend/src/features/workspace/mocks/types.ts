import type { MeetingParticipant, TaskStatus, TranscriptLine, Visibility } from "../domain/content-contract";
import type { Invitation, Member, Project, Team, Workspace } from "../domain/contract";
import type { KnowledgeItem } from "../domain/knowledge-contract";

/** A member as stored: the account behind them is what ties one person's workspaces together. */
export type StoredMember = Member & { account_id: string };

/** A recording shared into a workspace, with what Leo found in it. Its id is the recording's id. */
export type StoredMeeting = {
  id: string;
  title: string;
  started_at: string;
  duration_minutes: number;
  /** The account that recorded it and owns it. */
  owner_account_id: string;
  organizer_id: string;
  participants: MeetingParticipant[];
  visibility: Visibility;
  project_id: string | null;
  transcript_shared: boolean;
  summary: string;
  key_points: string[];
  transcript: TranscriptLine[];
};

export type StoredDecision = { id: string; text: string; meeting_id: string; superseded_by: string | null };

export type StoredTask = {
  id: string;
  title: string;
  status: TaskStatus;
  assignee_id: string | null;
  due_on: string | null;
  project_id: string | null;
  meeting_id: string | null;
  created_at: string;
};

/** What happened in a workspace, for the platform's event log. Names are kept as they were then. */
export const WORKSPACE_EVENT_ACTIONS = [
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
export type WorkspaceEventAction = (typeof WORKSPACE_EVENT_ACTIONS)[number];

export type WorkspaceEvent = {
  id: string;
  at: string;
  action: WorkspaceEventAction;
  /** Who did it: a member's name, or null when the platform's team did. */
  actor: string | null;
  /** Who or what it was done to: a name, an email, a file; null when nothing else is needed. */
  target: string | null;
  /** The new value where there is one: a role ("admin"), seats ("12"), the settings changed ("sharing"). */
  value: string | null;
};

export const BILLING_STANDINGS = ["active", "trialing", "past_due"] as const;
export type BillingStanding = (typeof BILLING_STANDINGS)[number];

/** What the platform's team controls; the workspace's own members don't manage it. */
export type WorkspaceControl = {
  /** Access is paused for every member; the reason is the platform team's own note. */
  suspended: { at: string; reason: string } | null;
  billing: BillingStanding;
  /** Set while `billing` is "trialing". */
  trial_ends_at: string | null;
  /** Newest first. */
  events: WorkspaceEvent[];
};

/** Everything one workspace holds in the demo. */
export type WorkspaceData = {
  workspace: Workspace;
  members: StoredMember[];
  invitations: Invitation[];
  teams: Team[];
  projects: Project[];
  meetings: StoredMeeting[];
  decisions: StoredDecision[];
  tasks: StoredTask[];
  knowledge: KnowledgeItem[];
  usage: Record<string, [meetings: number, minutes: number]>;
  control: WorkspaceControl;
};

/** A meeting fixture: the meeting plus its decisions and tasks, people by name. */
export type MeetingSeed = Omit<StoredMeeting, "participants" | "organizer_id" | "owner_account_id"> & {
  owner: string;
  participants: string[];
  decisions: string[];
  actions: { text: string; owner: string | null; status: TaskStatus; dueIn: number | null }[];
};
