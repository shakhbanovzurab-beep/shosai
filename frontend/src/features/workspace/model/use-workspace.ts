"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";

import type { WorkspaceState } from "../domain/contract";
import { workspacePath } from "../domain/paths";
import { type Permissions, permissionsOf } from "../domain/roles";
import { resourcesOf } from "./resources";
import { useWorkspaceRef } from "./workspace-context";

/**
 * The current workspace, what the signed-in member may do in it, its resources and its links. Only
 * for components under `WorkspaceGate`, which renders its children once the workspace is loaded.
 */
export function useWorkspace(): {
  ws: string;
  slug: string;
  state: WorkspaceState;
  can: Permissions;
  path: (path?: string) => string;
} {
  const { id, slug } = useWorkspaceRef();
  const resource = usePollingResource(resourcesOf(id).state);
  if (resource.status !== "ready") throw new Error("useWorkspace must be used inside WorkspaceGate.");
  const state = resource.data;
  return { ws: id, slug, state, can: permissionsOf(state), path: (path = "") => workspacePath(slug, path) };
}

/** The current workspace's resources, for refreshing after an error. */
export const useResources = () => resourcesOf(useWorkspaceRef().id);

export const useMeetings = () => usePollingResource(useResources().meetings);
export const useDecisions = () => usePollingResource(useResources().decisions);
export const useTasks = () => usePollingResource(useResources().tasks);
export const useKnowledge = () => usePollingResource(useResources().knowledge);
export const useUsage = () => usePollingResource(useResources().usage);

export function useMeetingDetail(id: string) {
  const ref = useWorkspaceRef();
  return usePollingResource(resourcesOf(ref.id).meeting(id));
}
