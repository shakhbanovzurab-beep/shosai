"use client";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";
import { errorMessage } from "@/lib/errors";

import { accountApi } from "../api/workspace-api";
import type { CreateWorkspaceRequest, UpdateWorkspaceRequest, WorkspaceState } from "../domain/contract";
import { forgetWorkspace, refreshAccount, resourcesOf } from "./resources";
import type { WorkspaceWords } from "./words";

export const applyState = (state: WorkspaceState) => resourcesOf(state.workspace.id).state.update(() => state);

/** Creates a workspace; resolves to its slug, or to the message to show in the form. */
export async function createWorkspace(
  request: CreateWorkspaceRequest,
  t: WorkspaceWords,
): Promise<{ slug: string } | { error: string }> {
  try {
    const state = await accountApi.create(request);
    refreshAccount();
    toast.success(t("toasts.workspaceReady", { name: request.name }), {
      description: t("toasts.workspaceReadyHint"),
    });
    return { slug: state.workspace.slug };
  } catch (error) {
    return { error: errorMessage(error) ?? t("toasts.createWorkspaceFailed") };
  }
}

/** Saves workspace settings and confirms with `message`; resolves to whether it worked. */
export async function updateWorkspace(ws: string, request: UpdateWorkspaceRequest, message: string, t: WorkspaceWords) {
  try {
    applyState(await resourcesOf(ws).api.update(request));
    refreshAccount();
    toast.success(message);
    return true;
  } catch (error) {
    toast.error(t("toasts.saveFailed"), { description: apiErrorDescription(error) });
    return false;
  }
}

async function goAway(ws: string, call: () => Promise<void>, done: string, failed: string) {
  try {
    await call();
    forgetWorkspace(ws);
    refreshAccount();
    toast.success(done);
    return true;
  } catch (error) {
    toast.error(failed, { description: apiErrorDescription(error) });
    return false;
  }
}

export const deleteWorkspace = (ws: string, name: string, t: WorkspaceWords) =>
  goAway(ws, resourcesOf(ws).api.remove, t("toasts.workspaceDeleted", { name }), t("toasts.deleteWorkspaceFailed"));

export const leaveWorkspace = (ws: string, name: string, t: WorkspaceWords) =>
  goAway(ws, resourcesOf(ws).api.leave, t("toasts.workspaceLeft", { name }), t("toasts.leaveWorkspaceFailed"));
