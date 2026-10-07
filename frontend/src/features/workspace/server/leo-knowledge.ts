import type { TeamMeeting } from "../domain/content-contract";
import type { WorkspaceRef } from "../domain/contract";
import type { KnowledgeItem } from "../domain/knowledge-contract";
import { canUseKnowledge } from "../domain/visibility";
import { activeMembership, activeWorkspaces, meIn } from "./demo-store";
import { refOf } from "./personal";
import { listMeetings } from "./projection";
import type { StoredMember, WorkspaceData } from "./types";

/*
 * What Leo may read in workspaces for the account. The permission check happens here, before
 * anything reaches the model. Admin rights don't widen it: Leo answers as a member.
 */

export type LeoWorkspaceKnowledge = {
  workspace: WorkspaceRef;
  /** Knowledge the account can use as a member: for everyone, its teams, or added by it. */
  usable: KnowledgeItem[];
  /** The usable knowledge whose names match the question. */
  matched: KnowledgeItem[];
  /** Meetings the account can open whose titles match the question. */
  meetings: Pick<TeamMeeting, "id" | "title">[];
  /** Knowledge in the workspace Leo won't read for this account (other teams' private knowledge). */
  hidden: number;
};

const words = (text: string) => text.toLowerCase().match(/[a-z0-9]{4,}/g) ?? [];

function knowledgeIn(data: WorkspaceData, me: StoredMember, question: string): LeoWorkspaceKnowledge {
  const usable = data.knowledge.filter((k) => k.status === "ready" && canUseKnowledge(me, false, k));
  const asked = new Set(words(question));
  const matches = (name: string) => words(name).some((w) => asked.has(w));
  return {
    workspace: refOf(data),
    usable,
    matched: usable.filter((k) => matches(k.name)),
    meetings: listMeetings(data, me)
      .filter((m) => matches(m.title))
      .map(({ id, title }) => ({ id, title })),
    hidden: data.knowledge.length - usable.length,
  };
}

/** Inside one workspace: only that workspace's knowledge and meetings. */
export function leoKnowledge(workspaceId: string, question: string): LeoWorkspaceKnowledge | null {
  const found = activeMembership(workspaceId);
  return found ? knowledgeIn(found.data, found.me, question) : null;
}

/** In Personal: what every workspace of the account lets it use, each labeled with its workspace. */
export function leoKnowledgeEverywhere(question: string): LeoWorkspaceKnowledge[] {
  return activeWorkspaces().flatMap((data) => {
    const me = meIn(data);
    return me ? [knowledgeIn(data, me, question)] : [];
  });
}
