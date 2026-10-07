import type { Decision, Task, TeamMeeting, UpcomingMeeting } from "./content-contract";
import type { WorkspaceState } from "./contract";
import type { KnowledgeItem } from "./knowledge-contract";

export type SetupStepId = "invite" | "sharing" | "share" | "knowledge";

/** A step by its code; the UI words it (`setup.steps.<id>`). */
export type SetupStep = { id: SetupStepId; done: boolean };

/**
 * The first steps of a new workspace, shown on Home to admins until they are all done. Each one is
 * worked out from the workspace itself, so the list stays right whoever completes a step.
 */
export function setupSteps(state: WorkspaceState, meetings: TeamMeeting[], knowledge: KnowledgeItem[]): SetupStep[] {
  return [
    {
      id: "invite",
      done: state.members.length + state.invitations.length >= 3,
    },
    {
      id: "sharing",
      done: state.workspace.sharing_reviewed,
    },
    {
      id: "share",
      done: meetings.some((m) => m.organizer_id === state.me_id),
    },
    {
      id: "knowledge",
      done: knowledge.length > 0,
    },
  ];
}

/** Nothing shared, scheduled, decided or assigned yet: Home shows one line instead of empty blocks. */
export const isQuietStart = (
  meetings: TeamMeeting[],
  upcoming: UpcomingMeeting[],
  decisions: Decision[],
  tasks: Task[],
  projectCount: number,
) =>
  meetings.length === 0 && upcoming.length === 0 && decisions.length === 0 && tasks.length === 0 && projectCount === 0;
