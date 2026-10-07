import type { Decision, Task, TeamMeeting, TeamMeetingDetail } from "../domain/content-contract";
import type { Member } from "../domain/contract";
import { isAdmin } from "../domain/roles";
import { canSee } from "../domain/visibility";
import type { StoredDecision, StoredMeeting, StoredTask, WorkspaceData } from "./types";

/* What one member sees of a workspace's meetings, decisions and tasks, in the API's shape. */

const teamOf = (meeting: StoredMeeting) => (meeting.visibility.level === "team" ? meeting.visibility.team_id : null);

const visibleMeetings = (data: WorkspaceData, viewer: Member) => data.meetings.filter((m) => canSee(viewer, m));

function toDecision(decision: StoredDecision, meeting: StoredMeeting): Decision {
  return {
    ...decision,
    meeting_title: meeting.title,
    decided_at: meeting.started_at,
    team_id: teamOf(meeting),
    project_id: meeting.project_id,
    participants: meeting.participants.map((p) => p.name),
  };
}

function toSummary(data: WorkspaceData, meeting: StoredMeeting): TeamMeeting {
  const { key_points: _points, transcript: _transcript, owner_account_id: _owner, ...rest } = meeting;
  return {
    ...rest,
    external: meeting.participants.some((p) => p.member_id === null),
    decision_count: data.decisions.filter((d) => d.meeting_id === meeting.id).length,
    task_count: data.tasks.filter((t) => t.meeting_id === meeting.id).length,
  };
}

/**
 * Who sees a task: anyone who can open the meeting it came from; everyone for a task added to a
 * project by hand; its assignee always. A task whose meeting was withdrawn stays with its assignee
 * and the admins, so the meeting's audience never widens.
 */
function canSeeTask(data: WorkspaceData, viewer: Member, task: StoredTask) {
  if (task.assignee_id === viewer.id) return true;
  if (task.meeting_id === null) return true;
  const meeting = data.meetings.find((m) => m.id === task.meeting_id);
  return meeting ? canSee(viewer, meeting) : isAdmin(viewer);
}

export function toTask(data: WorkspaceData, viewer: Member, task: StoredTask): Task {
  const meeting = task.meeting_id ? data.meetings.find((m) => m.id === task.meeting_id) : undefined;
  const open = meeting && canSee(viewer, meeting) ? meeting : undefined;
  return {
    ...task,
    meeting_title: open?.title ?? null,
    team_id: meeting ? teamOf(meeting) : null,
  };
}

export const listMeetings = (data: WorkspaceData, viewer: Member) =>
  visibleMeetings(data, viewer).map((m) => toSummary(data, m));

export function meetingDetail(data: WorkspaceData, viewer: Member, id: string): TeamMeetingDetail | null {
  const meeting = data.meetings.find((m) => m.id === id);
  if (!meeting || !canSee(viewer, meeting)) return null;
  return {
    ...toSummary(data, meeting),
    key_points: meeting.key_points,
    decisions: data.decisions.filter((d) => d.meeting_id === id).map((d) => toDecision(d, meeting)),
    tasks: data.tasks.filter((t) => t.meeting_id === id).map((t) => toTask(data, viewer, t)),
    transcript: meeting.transcript_shared || meeting.organizer_id === viewer.id ? meeting.transcript : null,
  };
}

export function listDecisions(data: WorkspaceData, viewer: Member) {
  const meetings = new Map(visibleMeetings(data, viewer).map((m) => [m.id, m]));
  return data.decisions.flatMap((d) => {
    const meeting = meetings.get(d.meeting_id);
    return meeting ? [toDecision(d, meeting)] : [];
  });
}

export const listTasks = (data: WorkspaceData, viewer: Member) =>
  data.tasks.filter((t) => canSeeTask(data, viewer, t)).map((t) => toTask(data, viewer, t));

/** A task the member may see (and therefore change), or null. */
export function taskFor(data: WorkspaceData, viewer: Member, id: string) {
  const task = data.tasks.find((t) => t.id === id);
  return task && canSeeTask(data, viewer, task) ? task : null;
}
