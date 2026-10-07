"use client";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { platformPromptsApi } from "../api/platform-prompts-api";
import type { PlatformPromptConfig, PlatformPromptsState, PlatformPromptVersion } from "../domain/contract";
import { platformPromptsResource } from "./platform-prompts-store";

/** Saves the draft and keeps the loaded state in step with what the server stored. */
export async function persist(config: PlatformPromptConfig) {
  const draft = await platformPromptsApi.saveDraft(config);
  platformPromptsResource.update((data) => ({ ...data, draft }));
}

/* Server actions with their toasts; each resolves to the new state, or null when it failed. */

export async function publishDraft(flush: () => Promise<boolean>, comment: string) {
  if (!(await flush())) {
    toast.error("Черновик не сохранён", { description: "Повторите сохранение и попробуйте опубликовать снова." });
    return null;
  }
  try {
    const state = await platformPromptsApi.publish({ comment });
    toast.success("Версия опубликована", { description: "Новые настройки применяются ко всем пользователям." });
    return state;
  } catch (error) {
    toast.error("Не удалось опубликовать", { description: errorMessage(error) });
    return null;
  }
}

export async function restoreVersion(discard: () => Promise<void>, version: PlatformPromptVersion) {
  try {
    await discard();
    const state = await platformPromptsApi.restore(version.id);
    toast.success(`Восстановлена версия ${version.number}`, { description: "Она опубликована как новая версия." });
    return state;
  } catch (error) {
    toast.error("Не удалось откатить", { description: errorMessage(error) });
    return null;
  }
}

/** Puts the published config back into the draft, without publishing anything. */
export async function resetDraft(discard: () => Promise<void>, data: PlatformPromptsState) {
  if (!data.published) return null;
  try {
    await discard();
    const draft = await platformPromptsApi.saveDraft(data.published.config);
    toast.success("Изменения отменены", { description: "Черновик совпадает с опубликованной версией." });
    return { ...data, draft };
  } catch (error) {
    toast.error("Не удалось отменить изменения", { description: errorMessage(error) });
    return null;
  }
}
