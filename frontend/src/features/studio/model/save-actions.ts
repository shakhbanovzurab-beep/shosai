import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";

import { studioApi } from "../api/studio-api";
import type { RoleModelSettings } from "../domain/contract";
import { contextResource, modelsResource } from "./studio-resources";
import type { StudioWords } from "./words";

/** The context editor's autosave: rejects on failure so the editor can offer a retry. */
export async function saveContext(content: string) {
  const saved = await studioApi.saveContext(content);
  contextResource.update(() => saved);
}

/** Saves a role's model settings straight away, showing the change at once and rolling back if the server refuses. */
export async function saveRoleSettings(next: RoleModelSettings, previous: RoleModelSettings, t: StudioWords) {
  const swap = (value: RoleModelSettings) =>
    modelsResource.update((data) => ({ ...data, roles: data.roles.map((r) => (r.role === value.role ? value : r)) }));
  swap(next);
  try {
    const { role, ...body } = next;
    swap(await studioApi.updateRole(role, body));
  } catch (error) {
    swap(previous);
    toast.error(t("models.saveFailed"), { description: apiErrorDescription(error) });
  }
}
