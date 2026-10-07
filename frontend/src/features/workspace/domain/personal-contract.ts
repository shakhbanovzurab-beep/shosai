/**
 * The account's own view across its workspaces: what Personal shows of them without mixing them into
 * personal data. Served at `/api/me/*`. See docs/workspace-api.md.
 *
 * GET /me/tasks     → MyTasksResponse      (tasks assigned to the account, in every workspace)
 * GET /me/meetings  → MyMeetingsResponse   (meetings others shared with the account, per workspace)
 * GET /me/shares    → MySharesResponse     (where the account's recordings and files are shared)
 * GET /me/knowledge → MyKnowledgeResponse  (what Leo may use from each workspace when the account is in Personal)
 */

import type { Task, TaskStatus, TeamMeeting, Visibility } from "./content-contract";
import type { WorkspaceRef } from "./contract";
import type { KnowledgeAccess, KnowledgeItem } from "./knowledge-contract";

/** A workspace task assigned to the account, with where it lives. Changing it changes the original. */
export type MyTask = Task & { workspace: WorkspaceRef; project_name: string | null };

export type MyTasksResponse = { tasks: MyTask[] };

/** Meetings in one workspace the account can open and didn't record itself. */
export type WorkspaceMeetings = { workspace: WorkspaceRef; meetings: TeamMeeting[] };

export type MyMeetingsResponse = { workspaces: WorkspaceMeetings[] };

/** One of the account's recordings, shared into a workspace. */
export type RecordingShare = {
  recording_id: string;
  workspace: WorkspaceRef;
  visibility: Visibility;
  project_id: string | null;
  transcript_shared: boolean;
  /** Its tasks, live: the same objects the workspace sees. */
  tasks: { id: string; title: string; status: TaskStatus; assignee_name: string | null }[];
};

/** One of the account's files, shared in a workspace's knowledge. */
export type FileShare = { file_id: string; workspace: WorkspaceRef; item_id: string; access: KnowledgeAccess };

export type MySharesResponse = { recordings: RecordingShare[]; files: FileShare[] };

/**
 * One workspace's knowledge Leo may use for the account in Personal: what it may use there as a
 * member (admin rights don't widen it), plus how many meetings, decisions and projects it can open.
 */
export type WorkspaceKnowledge = {
  workspace: WorkspaceRef;
  items: KnowledgeItem[];
  meetings: number;
  decisions: number;
  projects: number;
};

export type MyKnowledgeResponse = { workspaces: WorkspaceKnowledge[] };
