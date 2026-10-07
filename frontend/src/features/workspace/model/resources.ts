"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { accountApi, workspaceApi } from "../api/workspace-api";
import type { TeamMeetingDetail } from "../domain/content-contract";

/* Client resources: the account's workspaces and Personal's view of them, then one set per workspace. */

export const workspacesResource = createPollingResource(accountApi.workspaces);
export const myTasksResource = createPollingResource(accountApi.myTasks);
export const myMeetingsResource = createPollingResource(accountApi.myMeetings);
export const mySharesResource = createPollingResource(accountApi.myShares);
export const myKnowledgeResource = createPollingResource(accountApi.myKnowledge);

export const useWorkspaces = () => usePollingResource(workspacesResource);
export const useMyTasks = () => usePollingResource(myTasksResource);
export const useMyMeetings = () => usePollingResource(myMeetingsResource);
export const useMyShares = () => usePollingResource(mySharesResource);
export const useMyKnowledge = () => usePollingResource(myKnowledgeResource);

function createWorkspaceResources(ws: string) {
  const api = workspaceApi(ws);
  const meetingDetails = new Map<string, PollingResource<TeamMeetingDetail | null>>();
  return {
    api,
    state: createPollingResource(api.get),
    meetings: createPollingResource(api.meetings),
    decisions: createPollingResource(api.decisions),
    tasks: createPollingResource(api.tasks),
    knowledge: createPollingResource(api.knowledge, (data) => data.items.some((i) => i.status === "indexing")),
    usage: createPollingResource(api.usage),
    /** One resource per opened meeting, kept so going back shows it at once. */
    meeting(id: string) {
      let resource = meetingDetails.get(id);
      if (!resource) {
        resource = createPollingResource(() => api.meeting(id));
        meetingDetails.set(id, resource);
      }
      return resource;
    },
    forgetMeetings: () => meetingDetails.clear(),
  };
}

export type WorkspaceResources = ReturnType<typeof createWorkspaceResources>;

const cache = new Map<string, WorkspaceResources>();

/** The resources of one workspace, made on first use. */
export function resourcesOf(ws: string): WorkspaceResources {
  let resources = cache.get(ws);
  if (!resources) {
    resources = createWorkspaceResources(ws);
    cache.set(ws, resources);
  }
  return resources;
}

/** After leaving or deleting a workspace: nothing of it stays loaded. */
export const forgetWorkspace = (ws: string) => cache.delete(ws);

/** After sharing changes in a workspace: its lists, and Personal's view of the account's things. */
export function refreshShared(ws: string) {
  const r = resourcesOf(ws);
  void r.meetings.refresh();
  void r.decisions.refresh();
  void r.tasks.refresh();
  void mySharesResource.refresh();
  void myTasksResource.refresh();
}

/** After one of the account's files is shared, deleted or handed over: where its files are, and what Leo may use. */
export function refreshFileShares() {
  void mySharesResource.refresh();
  void myKnowledgeResource.refresh();
  for (const resources of cache.values()) void resources.knowledge.refresh();
}

/** After the account joins, creates, leaves or deletes a workspace. */
export function refreshAccount() {
  void workspacesResource.refresh();
  void myTasksResource.refresh();
  void myMeetingsResource.refresh();
  void mySharesResource.refresh();
  void myKnowledgeResource.refresh();
}
