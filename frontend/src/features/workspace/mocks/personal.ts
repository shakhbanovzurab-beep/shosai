import type { TaskStatus } from "../domain/content-contract";
import type { WorkspaceRef } from "../domain/contract";
import type { MyKnowledgeResponse, MyMeetingsResponse, MySharesResponse, MyTask } from "../domain/personal-contract";
import { canUseKnowledge } from "../domain/visibility";
import { ME_ACCOUNT } from "./demo-people";
import { activeMembership, activeWorkspaces, meIn, memberName } from "./demo-store";
import { listDecisions, listMeetings, toTask } from "./projection";
import type { WorkspaceData } from "./types";

/* The account's view across its workspaces: what Personal shows, and what Kanban and Leo use. */

export const refOf = (data: WorkspaceData): WorkspaceRef => ({
  id: data.workspace.id,
  slug: data.workspace.slug,
  name: data.workspace.name,
});

/** Every task assigned to the account, in every workspace it can use. */
export function myTasks(): MyTask[] {
  return activeWorkspaces().flatMap((data) => {
    const me = meIn(data);
    if (!me) return [];
    return data.tasks
      .filter((t) => t.assignee_id === me.id)
      .map((t) => ({
        ...toTask(data, me, t),
        workspace: refOf(data),
        project_name: data.projects.find((p) => p.id === t.project_id)?.name ?? null,
      }));
  });
}

/** Changes one of the account's tasks from Personal (Kanban, Productivity): the workspace's own task. */
export function updateMyTask(workspaceId: string, taskId: string, patch: { status?: TaskStatus; title?: string }) {
  const found = activeMembership(workspaceId);
  const task = found?.data.tasks.find((t) => t.id === taskId && t.assignee_id === found.me.id);
  if (!found || !task) return null;
  if (patch.status) task.status = patch.status;
  if (patch.title) task.title = patch.title;
  return myTasks().find((t) => t.id === taskId && t.workspace.id === workspaceId) ?? null;
}

/** Meetings others shared with the account, per workspace; its own recordings are in its Notes already. */
export function myMeetings(): MyMeetingsResponse {
  return {
    workspaces: activeWorkspaces().flatMap((data) => {
      const me = meIn(data);
      if (!me) return [];
      return [{ workspace: refOf(data), meetings: listMeetings(data, me).filter((m) => m.organizer_id !== me.id) }];
    }),
  };
}

/** Where the account's recordings and files are shared, with the tasks its recordings produced. */
export function myShares(): MySharesResponse {
  const result: MySharesResponse = { recordings: [], files: [] };
  for (const data of activeWorkspaces()) {
    const me = meIn(data);
    if (!me) continue;
    for (const meeting of data.meetings.filter((m) => m.owner_account_id === ME_ACCOUNT)) {
      result.recordings.push({
        recording_id: meeting.id,
        workspace: refOf(data),
        visibility: meeting.visibility,
        project_id: meeting.project_id,
        transcript_shared: meeting.transcript_shared,
        tasks: data.tasks
          .filter((t) => t.meeting_id === meeting.id)
          .map((t) => ({ id: t.id, title: t.title, status: t.status, assignee_name: memberName(data, t.assignee_id) })),
      });
    }
    for (const item of data.knowledge) {
      if (item.source.kind !== "personal" || item.added_by !== me.id) continue;
      result.files.push({
        file_id: item.source.file_id,
        workspace: refOf(data),
        item_id: item.id,
        access: item.access,
      });
    }
  }
  return result;
}

/** Per workspace, what Leo may use for the account in Personal: as a member, never more. */
export function myKnowledge(): MyKnowledgeResponse {
  return {
    workspaces: activeWorkspaces().flatMap((data) => {
      const me = meIn(data);
      if (!me) return [];
      return [
        {
          workspace: refOf(data),
          items: data.knowledge.filter((k) => k.status === "ready" && canUseKnowledge(me, false, k)),
          meetings: listMeetings(data, me).length,
          decisions: listDecisions(data, me).length,
          projects: data.projects.length,
        },
      ];
    }),
  };
}

/**
 * A seat the account holds in a workspace on a paid plan. Team covers each member's own tools as
 * well, so Personal gets those entitlements too (unlimited meetings, File Manager, knowledge for Leo).
 */
export function accountSeat(): { workspace_name: string; plan: string } | null {
  const data = activeWorkspaces()[0];
  return data ? { workspace_name: data.workspace.name, plan: data.workspace.plan.name.toLowerCase() } : null;
}
