import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";

import { studioApi } from "../api/studio-api";
import type { Prompt, PromptDraft } from "../domain/contract";
import { promptsResource } from "./studio-resources";
import type { PromptWords, StudioWords } from "./words";

const refresh = () => void promptsResource.refresh();

export async function removePrompt(prompt: Prompt, t: PromptWords) {
  try {
    await studioApi.deletePrompt(prompt.id);
    toast.success(t("toasts.deleted", { name: prompt.name }));
  } catch (error) {
    toast.error(t("toasts.deleteFailed"), { description: apiErrorDescription(error) });
  }
  refresh();
}

/** Makes the prompt the one its role plays by, or sends the role back to its built-in default. */
export async function setPromptInUse(prompt: Prompt, use: boolean, t: PromptWords, studio: StudioWords) {
  try {
    const next = await studioApi.setActive({ role: prompt.role, prompt_id: use ? prompt.id : null });
    promptsResource.update(() => next);
    const role = studio(`roles.${prompt.role}.name`);
    toast.success(use ? t("toasts.inUse", { role, name: prompt.name }) : t("toasts.backToDefault", { role }));
  } catch (error) {
    toast.error(t("toasts.changeFailed"), { description: apiErrorDescription(error) });
  }
}

/** Creates a prompt; resolves true once it is saved so the editor can close. */
export async function createPrompt(draft: PromptDraft, t: PromptWords) {
  try {
    await studioApi.createPrompt(draft);
    refresh();
    toast.success(t("toasts.created", { name: draft.name }));
    return true;
  } catch (error) {
    toast.error(t("toasts.createFailed"), { description: apiErrorDescription(error) });
    return false;
  }
}

/** The editor's autosave: rejects on failure so the editor can offer a retry. */
export async function savePromptDraft(id: string, draft: PromptDraft) {
  await studioApi.updatePrompt(id, draft);
  refresh();
}
