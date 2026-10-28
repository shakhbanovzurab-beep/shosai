import { toast } from "sonner";

import { studioApi } from "../api/studio-api";
import type { Prompt, PromptDraft } from "../domain/contract";
import { describeStudioError, type ProblemWords } from "./studio-problem-words";
import { promptsResource } from "./studio-resources";
import type { PromptWords } from "./words";

const refresh = () => void promptsResource.refresh();

export async function removePrompt(prompt: Prompt, t: PromptWords, words: ProblemWords) {
  try {
    await studioApi.deletePrompt(prompt.id);
    toast.success(t("toasts.deleted", { name: prompt.name }));
  } catch (error) {
    toast.error(t("toasts.deleteFailed"), { description: describeStudioError(error, words) });
  }
  refresh();
}

/** Делает промт тем, по которому играет его роль, или возвращает роли встроенный промт. */
export async function setPromptInUse(prompt: Prompt, use: boolean, t: PromptWords, words: ProblemWords) {
  try {
    const next = await studioApi.setActive(prompt.role, use ? prompt.id : null);
    promptsResource.update(() => next);
    const role = words.studio(`roles.${prompt.role}.name`);
    toast.success(use ? t("toasts.inUse", { role, name: prompt.name }) : t("toasts.backToDefault", { role }));
  } catch (error) {
    toast.error(t("toasts.changeFailed"), { description: describeStudioError(error, words) });
  }
}

/**
 * Создаёт промт; true — сохранён, редактор можно закрыть. Ключ — один на попытку с этим черновиком: повтор после
 * сбоя сети не создаст второй промт.
 */
export async function createPrompt(draft: PromptDraft, idempotencyKey: string, t: PromptWords, words: ProblemWords) {
  try {
    await studioApi.createPrompt(draft, idempotencyKey);
    refresh();
    toast.success(t("toasts.created", { name: draft.name }));
    return true;
  } catch (error) {
    toast.error(t("toasts.createFailed"), { description: describeStudioError(error, words) });
    return false;
  }
}

/** Автосохранение редактора: отклоняется при сбое, чтобы редактор предложил повтор. */
export async function savePromptDraft(id: string, draft: PromptDraft) {
  await studioApi.updatePrompt(id, draft);
  refresh();
}
