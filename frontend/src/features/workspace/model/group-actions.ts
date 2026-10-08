"use client";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";
import { errorMessage } from "@/lib/errors";

import type { ProjectInput, Team, TeamInput } from "../domain/contract";
import { refreshShared, resourcesOf } from "./resources";
import { failureText, type MembersWords, words } from "./words";
import { applyState } from "./workspace-actions";

/** Creates or updates a team; resolves to null on success or the message to show in the dialog. */
export async function saveTeam(
  ws: string,
  teamId: string | null,
  input: TeamInput,
  t: MembersWords,
): Promise<string | null> {
  const { api } = resourcesOf(ws);
  try {
    applyState(teamId ? await api.updateTeam(teamId, input) : await api.createTeam(input));
    toast.success(t(teamId ? "toasts.teamSaved" : "toasts.teamCreated", { name: input.name }));
    return null;
  } catch (error) {
    return errorMessage(error) ?? t("toasts.teamSaveFailed");
  }
}

export async function deleteTeam(ws: string, team: Team, t: MembersWords) {
  try {
    applyState(await resourcesOf(ws).api.deleteTeam(team.id));
    // Meetings shared with the team now go to their participants only.
    refreshShared(ws);
    toast.success(t("toasts.teamDeleted", { name: team.name }));
    return true;
  } catch (error) {
    toast.error(t("toasts.teamDeleteFailed"), { description: apiErrorDescription(error) });
    return false;
  }
}

/** Creates or updates a project; resolves to its id, or to the message to show. New projects come first. */
export async function saveProject(
  ws: string,
  projectId: string | null,
  input: Partial<ProjectInput>,
  message?: string,
): Promise<{ id: string } | { error: string }> {
  const { api } = resourcesOf(ws);
  try {
    const state = projectId
      ? await api.updateProject(projectId, input)
      : await api.createProject(input as ProjectInput);
    applyState(state);
    if (message) toast.success(message);
    return { id: projectId ?? state.projects[0]?.id ?? "" };
  } catch (error) {
    const text = failureText(error);
    if (projectId)
      toast.error(
        words((t) => t("toasts.projectSaveFailed")),
        { description: text },
      );
    return { error: text };
  }
}

/** Deletes a project; its meetings and tasks stay, without a project. */
export async function deleteProject(ws: string, projectId: string, name: string) {
  try {
    applyState(await resourcesOf(ws).api.deleteProject(projectId));
    refreshShared(ws);
    toast.success(
      words((t) => t("toasts.projectDeleted", { name })),
      { description: words((t) => t("toasts.projectDeletedHint")) },
    );
    return true;
  } catch (error) {
    toast.error(
      words((t) => t("toasts.projectDeleteFailed")),
      { description: apiErrorDescription(error) },
    );
    return false;
  }
}
