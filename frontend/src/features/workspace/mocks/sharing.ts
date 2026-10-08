import type { ShareRecordingRequest } from "../domain/content-contract";
import type { KnowledgeItem, ShareFileRequest } from "../domain/knowledge-contract";
import { sharedFileItem } from "./demo-knowledge";
import { findRecording, recordingSeed, seedMeeting } from "./demo-seed";
import { activeMembership, everyWorkspace } from "./demo-store";
import { logEvent } from "./events";
import type { StoredMeeting, StoredMember, WorkspaceData } from "./types";

/*
 * Personal objects in workspaces. A recording is shared into at most one workspace at a time and a
 * file can be shared in several; neither is copied, and both leave with their owner.
 */

/** Takes a recording out of whatever workspace it is shared in. Its decisions go with it; tasks stay. */
export function withdrawRecording(recordingId: string) {
  for (const data of everyWorkspace()) {
    if (!data.meetings.some((m) => m.id === recordingId)) continue;
    data.meetings = data.meetings.filter((m) => m.id !== recordingId);
    data.decisions = data.decisions.filter((d) => d.meeting_id !== recordingId);
  }
}

/** Shares one of the account's recordings here, moving it if it was shared elsewhere. */
export function shareRecording(
  data: WorkspaceData,
  me: StoredMember,
  request: ShareRecordingRequest,
): StoredMeeting | null {
  const note = findRecording(request.recording_id);
  if (!note) return null;
  const existing = data.meetings.find((m) => m.id === note.id);
  if (existing) {
    Object.assign(existing, {
      visibility: request.visibility,
      project_id: request.project_id,
      transcript_shared: request.transcript_shared,
    });
    return existing;
  }
  withdrawRecording(note.id);
  const seed = recordingSeed(note, {
    visibility: request.visibility,
    project: request.project_id,
    transcript: request.transcript_shared,
  });
  const { meeting, decisions, tasks } = seedMeeting(seed, data.members);
  meeting.organizer_id = me.id;
  meeting.owner_account_id = me.account_id;
  data.meetings.push(meeting);
  data.decisions.push(...decisions);
  // Shared again: the tasks it made last time are still here, so only the missing ones are added.
  const known = new Set(data.tasks.map((t) => t.id));
  data.tasks.push(...tasks.filter((t) => !known.has(t.id)));
  return meeting;
}

/** Shares one of the account's files here, or changes who can use it if it already is. */
export function shareFile(data: WorkspaceData, me: StoredMember, request: ShareFileRequest): KnowledgeItem {
  const existing = data.knowledge.find((k) => k.source.kind === "personal" && k.source.file_id === request.file_id);
  if (existing) {
    existing.access = request.access;
    existing.project_id = request.project_id;
    return existing;
  }
  const entry = sharedFileItem(request, me.id);
  data.knowledge.unshift(entry);
  return entry;
}

/** A file deleted (or handed to another workspace) by its owner disappears from every workspace it was shared in. */
export function withdrawFile(fileId: string) {
  for (const data of everyWorkspace())
    data.knowledge = data.knowledge.filter((k) => !(k.source.kind === "personal" && k.source.file_id === fileId));
}

/**
 * The owner hands a file they shared here over to the workspace: it becomes the workspace's own
 * upload and stays when they leave. False when the file isn't shared here by the account.
 */
export function adoptFile(workspaceId: string, fileId: string) {
  const found = activeMembership(workspaceId);
  const entry = found?.data.knowledge.find(
    (k) => k.source.kind === "personal" && k.source.file_id === fileId && k.added_by === found.me.id,
  );
  if (!found || !entry) return false;
  entry.source = { kind: "upload" };
  logEvent(found.data, "file_transferred", found.me, { target: entry.name });
  return true;
}

/**
 * Someone leaves or is removed: what they own leaves with them (shared recordings and files), the
 * work stays (tasks, now waiting for an owner, uploads and sources that belong to the workspace).
 */
export function withdrawMember(data: WorkspaceData, member: StoredMember) {
  const theirs = new Set(data.meetings.filter((m) => m.owner_account_id === member.account_id).map((m) => m.id));
  data.meetings = data.meetings.filter((m) => !theirs.has(m.id));
  data.decisions = data.decisions.filter((d) => !theirs.has(d.meeting_id));
  data.knowledge = data.knowledge.filter((k) => !(k.source.kind === "personal" && k.added_by === member.id));
  for (const task of data.tasks) if (task.assignee_id === member.id && task.status !== "done") task.assignee_id = null;
  for (const team of data.teams) if (team.lead_id === member.id) team.lead_id = null;
  for (const project of data.projects) if (project.lead_id === member.id) project.lead_id = null;
  data.members = data.members.filter((m) => m.id !== member.id);
}
