"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { workspacesApi } from "../api/workspaces-api";
import type { AdminWorkspaceDetail } from "../domain/contract";

export const workspacesResource = createPollingResource(workspacesApi.list);

const details = new Map<string, PollingResource<AdminWorkspaceDetail | null>>();

/** One resource per opened workspace, kept so going back shows it at once. */
export function workspaceResource(id: string) {
  let resource = details.get(id);
  if (!resource) {
    resource = createPollingResource(() => workspacesApi.get(id));
    details.set(id, resource);
  }
  return resource;
}

export const useWorkspaces = () => usePollingResource(workspacesResource);
export const useWorkspace = (id: string) => usePollingResource(workspaceResource(id));
