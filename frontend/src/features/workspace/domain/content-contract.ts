/**
 * What a workspace shares: meetings with their decisions, tasks, and knowledge. Every list is already
 * filtered to what the signed-in member may see. All paths are under `/workspaces/{ws}`.
 * See docs/workspace-api.md.
 *
 * GET    /meetings              → MeetingsResponse
 * POST   /meetings              → 201 TeamMeetingDetail   (ShareRecordingRequest: one of your recordings, moved here if shared elsewhere)
 * GET    /meetings/{id}         → TeamMeetingDetail       (404 when missing or not shared with you)
 * PATCH  /meetings/{id}         → TeamMeetingDetail       (MeetingShareRequest; organizer or admins)
 * DELETE /meetings/{id}         → 204                     (stop sharing: organizer; remove: admins)
 * GET    /decisions             → DecisionsResponse
 * GET    /tasks                 → TasksResponse
 * POST   /tasks                 → 201 Task                (TaskCreate)
 * PATCH  /tasks/{id}            → Task                    (TaskUpdate)
 * Knowledge types are in `knowledge-contract.ts`.
 *
 * GET    /knowledge             → KnowledgeResponse
 * POST   /knowledge             → 201 KnowledgeResponse   (multipart: `files`, `level`, `team_id`, `project_id`)
 * POST   /knowledge/publish     → 201 KnowledgeItem       (ShareFileRequest: one of your files, pointed to, not copied)
 * POST   /knowledge/sources     → 201 KnowledgeItem       (ConnectSourceRequest; admins)
 * PATCH  /knowledge/{id}        → KnowledgeItem           (KnowledgeUpdate; who added it, or admins)
 * DELETE /knowledge/{id}        → 204                     (removes an upload or a source, or stops sharing a file)
 * GET    /usage                 → UsageResponse           (admins)
 */

/**
 * Who can open a meeting's notes inside the workspace: the members who took part, a team, or
 * everyone. Its organizer always can. A recording nobody shared stays in its owner's Notes.
 */
export const SHARE_LEVELS = ["participants", "team", "workspace"] as const;
export type ShareLevel = (typeof SHARE_LEVELS)[number];

/** `team_id` is set only for the "team" level. */
export type Visibility = { level: ShareLevel; team_id: string | null };

export type MeetingParticipant = {
  name: string;
  /** Null for someone outside the workspace. */
  member_id: string | null;
};

/**
 * A recording shared into the workspace. It is the same object as in its owner's Notes (same id):
 * sharing doesn't copy it, and stopping sharing takes it back out.
 */
export type TeamMeeting = {
  id: string;
  title: string;
  started_at: string;
  duration_minutes: number;
  /** The member who recorded and shared it; they own it. */
  organizer_id: string;
  participants: MeetingParticipant[];
  /** Someone from outside the workspace took part. */
  external: boolean;
  visibility: Visibility;
  project_id: string | null;
  summary: string;
  decision_count: number;
  task_count: number;
  /** Whether people it is shared with can read the transcript, not only the summary. */
  transcript_shared: boolean;
};

export type TranscriptLine = { speaker: string; at: number; text: string };

export type TeamMeetingDetail = TeamMeeting & {
  key_points: string[];
  decisions: Decision[];
  tasks: Task[];
  /** Null when the organizer shared the summary only (the organizer always gets it). */
  transcript: TranscriptLine[] | null;
};

/** A meeting coming up, and where its notes will go once it ends. */
export type UpcomingMeeting = {
  id: string;
  title: string;
  start: string;
  end: string;
  participants: MeetingParticipant[];
  external: boolean;
  /** Null when the notes will stay with the organizer (guests attend, or the rule keeps them private). */
  shares_with: Visibility | null;
};

export type MeetingsResponse = { meetings: TeamMeeting[]; upcoming: UpcomingMeeting[] };

export type ShareRecordingRequest = {
  recording_id: string;
  visibility: Visibility;
  project_id: string | null;
  transcript_shared: boolean;
};

export type MeetingShareRequest = { visibility?: Visibility; transcript_shared?: boolean; project_id?: string | null };

export type Decision = {
  id: string;
  text: string;
  meeting_id: string;
  meeting_title: string;
  decided_at: string;
  /** The team the meeting is shared with; null for participants or everyone. */
  team_id: string | null;
  project_id: string | null;
  /** Names of the people who were there. */
  participants: string[];
  /** A later decision that replaced this one. */
  superseded_by: string | null;
};

export type DecisionsResponse = { decisions: Decision[] };

export const TASK_STATUSES = ["todo", "in_progress", "done"] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

/**
 * A piece of work in the workspace: agreed in a meeting or added to a project. Its assignee also sees
 * it in their personal Productivity and on the Kanban board they chose; it stays this one object.
 */
export type Task = {
  id: string;
  title: string;
  status: TaskStatus;
  /** Null while nobody owns it. */
  assignee_id: string | null;
  /** A calendar day, "2026-10-09"; null without a due date. */
  due_on: string | null;
  project_id: string | null;
  /** The meeting it was agreed in; null for a task added by hand. */
  meeting_id: string | null;
  /** Null when there is no meeting, or it's no longer shared with you. */
  meeting_title: string | null;
  /** The team of the meeting it came from. */
  team_id: string | null;
  created_at: string;
};

export type TasksResponse = { tasks: Task[] };

export const TASK_TITLE_MAX = 200;

export type TaskCreate = {
  title: string;
  assignee_id: string | null;
  due_on: string | null;
  project_id: string | null;
};

export type TaskUpdate = {
  title?: string;
  status?: TaskStatus;
  assignee_id?: string | null;
  due_on?: string | null;
  project_id?: string | null;
};

export type MemberUsage = { member_id: string; meetings: number; minutes: number };

export type UsageResponse = { month_start: string; members: MemberUsage[] };
