import { lumenKnowledge, northwindKnowledge } from "./demo-knowledge-seed";
import {
  LUMEN_SHARES,
  LUMEN_USAGE,
  lumenInvitations,
  lumenMembers,
  lumenProjects,
  lumenTeams,
  lumenWorkspace,
} from "./demo-lumen";
import { lumenMeetings } from "./demo-lumen-meetings";
import {
  NORTHWIND_USAGE,
  northwindMeetings,
  northwindMembers,
  northwindProjects,
  northwindWorkspace,
} from "./demo-northwind";
import { DAY, minutesAgo } from "./demo-people";
import { type ManualTask, manualTasks, myRecordings, recordingSeed, seedMeeting } from "./demo-seed";
import type { MeetingSeed, WorkspaceControl, WorkspaceData, WorkspaceEvent } from "./types";

/* The two workspaces the demo user is in, with their meetings, tasks and event log. */

type Seeded = Omit<WorkspaceData, "meetings" | "decisions" | "tasks" | "control">;

function withContent(data: Seeded, seeds: MeetingSeed[], manual: ManualTask[], control: WorkspaceControl) {
  const seeded = seeds.map((seed) => seedMeeting(seed, data.members));
  return {
    ...data,
    meetings: seeded.map((s) => s.meeting),
    decisions: seeded.flatMap((s) => s.decisions),
    tasks: [...seeded.flatMap((s) => s.tasks), ...manualTasks(manual)],
    control,
  } satisfies WorkspaceData;
}

const event = (id: string, action: WorkspaceEvent["action"], days: number, actor: string, extra = {}) =>
  ({ id, at: minutesAgo(days * DAY), action, actor, target: null, value: null, ...extra }) satisfies WorkspaceEvent;

export function seededLumen(): WorkspaceData {
  const shared = myRecordings().flatMap((note) => {
    const share = LUMEN_SHARES[note.id];
    return share ? [recordingSeed(note, share)] : [];
  });
  return withContent(
    {
      workspace: lumenWorkspace(),
      members: lumenMembers(),
      invitations: lumenInvitations(),
      teams: lumenTeams(),
      projects: lumenProjects(),
      knowledge: lumenKnowledge(),
      usage: { ...LUMEN_USAGE },
    },
    [...shared, ...lumenMeetings],
    [
      ["t-beta-email", "Prepare the beta announcement email", "m-arham", 8, "leo-beta", "todo"],
      ["t-agent-qa", "QA pass on the agent steps UI", "m-sofia", 3, "leo-beta", "in_progress"],
      ["t-scorecard", "Write the interview scorecard", "m-maya", 6, "hiring", "todo"],
      // Из командного чата «Release team» (TK-D13); источник — в моках канбана.
      ["t-chat-checklist", "Update the release checklist for 2.4", "m-arham", 2, "leo-beta", "todo"],
      ["t-chat-invites", "Send the beta invite list to support", "m-arham", 3, "leo-beta", "in_progress"],
    ],
    {
      suspended: null,
      billing: "active",
      trial_ends_at: null,
      events: [
        event("ev-l4", "member_invited", 1, "Arham Khan", { target: "lucas@lumen.so" }),
        event("ev-l3", "settings_changed", 12, "Arham Khan", { value: "sharing" }),
        event("ev-l2", "role_changed", 40, "Arham Khan", { target: "Maya Chen", value: "admin" }),
        event("ev-l1", "seats_changed", 90, "Arham Khan", { value: "8 → 10" }),
        event("ev-l0", "workspace_created", 337, "Arham Khan"),
      ],
    },
  );
}

export function seededNorthwind(): WorkspaceData {
  return withContent(
    {
      workspace: northwindWorkspace(),
      members: northwindMembers(),
      invitations: [],
      teams: [],
      projects: northwindProjects(),
      knowledge: northwindKnowledge(),
      usage: { ...NORTHWIND_USAGE },
    },
    northwindMeetings,
    [["t-training", "Prepare the pilot training session", "nw-arham", 9, "pilot", "todo"]],
    {
      suspended: null,
      billing: "active",
      trial_ends_at: null,
      events: [
        event("ev-n1", "member_invited", 20, "Liam Turner", { target: "arham@lumen.so, priya@lumen.so" }),
        event("ev-n0", "workspace_created", 21, "Liam Turner"),
      ],
    },
  );
}
