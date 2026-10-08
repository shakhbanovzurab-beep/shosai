import { meetingNotes as sampleMeetingNotes } from "@/features/notes/data/meeting-notes";
import type { MeetingNote } from "@/features/notes/domain/types";

import type { MeetingParticipant, TaskStatus, Visibility } from "../domain/content-contract";
import { dayFromNow, ME_ACCOUNT, PEOPLE } from "./demo-people";
import type { MeetingSeed, StoredDecision, StoredMeeting, StoredMember, StoredTask } from "./types";

/*
 * Turning recordings into workspace meetings. A shared recording keeps its id, so the meeting in the
 * workspace is the recording in its owner's Notes; its decisions and tasks get ids derived from it,
 * so sharing it again finds the tasks it already has instead of making new ones.
 */

/** Due dates of the sample action items, in days from today, so some are always overdue. */
const NOTE_DUE = [3, -4, 8, -1, 2, 5, 0, 10, 1, 6, -3, 4, 7];

/** Superseded decisions: the kickoff's pricing idea gave way to the workshop's. */
const SUPERSEDED: Record<string, string> = { "pricing-kickoff--d0": "pricing-workshop--d0" };

/** The demo user's recordings, as their Notes hold them. */
export const myRecordings = (): MeetingNote[] => sampleMeetingNotes;

export const findRecording = (id: string) => sampleMeetingNotes.find((note) => note.id === id) ?? null;

/** One of the demo user's recordings as a meeting fixture, shared with `visibility`. */
export function recordingSeed(
  note: MeetingNote,
  share: { visibility: Visibility; project: string | null; transcript: boolean },
): MeetingSeed {
  const offset = sampleMeetingNotes.indexOf(note) * 3;
  return {
    id: note.id,
    title: note.title,
    started_at: note.startedAt,
    duration_minutes: note.durationMinutes,
    owner: "Arham Khan",
    participants: note.participants.map((p) => p.name),
    visibility: share.visibility,
    project_id: share.project,
    transcript_shared: share.transcript,
    summary: note.summary,
    key_points: note.keyPoints,
    transcript: note.transcript,
    decisions: note.decisions,
    actions: note.actionItems.map((item, i) => {
      let status: TaskStatus = item.done ? "done" : "todo";
      // The first open item of the first recording is under way, so "In progress" shows up somewhere.
      if (!item.done && i === 0 && offset === 0) status = "in_progress";
      return { text: item.text, owner: item.owner, status, dueIn: NOTE_DUE[(offset + i) % NOTE_DUE.length] ?? null };
    }),
  };
}

export type SeededMeeting = { meeting: StoredMeeting; decisions: StoredDecision[]; tasks: StoredTask[] };

/** A fixture as stored in one workspace, matching people to its members by name. */
export function seedMeeting(
  { owner, participants, decisions, actions, ...rest }: MeetingSeed,
  members: StoredMember[],
) {
  const byName = new Map(members.map((m) => [m.name, m]));
  const people: MeetingParticipant[] = participants.map((name) => ({ name, member_id: byName.get(name)?.id ?? null }));
  const organizer = byName.get(owner);
  const meeting: StoredMeeting = {
    ...rest,
    owner_account_id: PEOPLE[owner]?.account ?? ME_ACCOUNT,
    organizer_id: organizer?.id ?? "",
    participants: people,
  };
  return {
    meeting,
    decisions: decisions.map((text, i) => {
      const id = `${rest.id}--d${i}`;
      return { id, text, meeting_id: rest.id, superseded_by: SUPERSEDED[id] ?? null };
    }),
    tasks: actions.map(
      (action, i): StoredTask => ({
        id: `${rest.id}--t${i}`,
        title: action.text,
        status: action.status,
        assignee_id: action.owner ? (byName.get(action.owner)?.id ?? null) : null,
        due_on: action.dueIn === null ? null : dayFromNow(action.dueIn),
        project_id: rest.project_id,
        meeting_id: rest.id,
        created_at: rest.started_at,
      }),
    ),
  } satisfies SeededMeeting;
}

export type ManualTask = [
  id: string,
  title: string,
  assignee: string | null,
  dueIn: number | null,
  project: string,
  status: TaskStatus,
];

/** Tasks added to projects by hand, not agreed in a meeting. */
export const manualTasks = (rows: ManualTask[]): StoredTask[] =>
  rows.map(([id, title, assignee_id, dueIn, project_id, status]) => ({
    id,
    title,
    status,
    assignee_id,
    due_on: dueIn === null ? null : dayFromNow(dueIn),
    project_id,
    meeting_id: null,
    created_at: "2026-10-01T09:00:00.000Z",
  }));
