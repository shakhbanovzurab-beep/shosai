"use client";

import { toast } from "sonner";

import { ApiError } from "@/lib/api/errors";

import { platformPromptsApi } from "../api/platform-prompts-api";
import type { PlatformConfig, PlatformPromptsState, VersionSummary } from "../domain/contract";
import { platformPromptsResource } from "./platform-prompts-store";
import { problemOf } from "./problem-description";

/** Сохраняет черновик и держит загруженное состояние в согласии с тем, что сохранил сервер. */
export async function persist(config: PlatformConfig) {
  const draft = await platformPromptsApi.saveDraft(config);
  platformPromptsResource.update((data) => ({ ...data, draft }));
}

// «Публиковать нечего» значит, что действующую версию уже сменили — например, в другой вкладке: экран её перечитывает.
function caughtUp(error: unknown) {
  if (error instanceof ApiError && error.code === "nothing_to_publish") void platformPromptsResource.refresh();
}

/* Действия на сервере с их тостами; каждое отдаёт новое состояние или null, если не вышло. */

export async function publishDraft(flush: () => Promise<boolean>, config: PlatformConfig, comment: string) {
  if (!(await flush())) {
    toast.error("Черновик не сохранён", { description: "Повторите сохранение и попробуйте опубликовать снова." });
    return null;
  }
  try {
    const state = await platformPromptsApi.publish(comment, crypto.randomUUID());
    toast.success("Версия опубликована", { description: "Leo получит её во всех разговорах в течение минуты." });
    return state;
  } catch (error) {
    caughtUp(error);
    toast.error("Не удалось опубликовать", { description: problemOf(error, config) });
    return null;
  }
}

export async function restoreVersion(discard: () => Promise<void>, config: PlatformConfig, version: VersionSummary) {
  try {
    await discard();
    const state = await platformPromptsApi.restore(version.id, crypto.randomUUID());
    toast.success(`Восстановлена версия ${version.number}`, { description: "Она опубликована как новая версия." });
    return state;
  } catch (error) {
    caughtUp(error);
    toast.error("Не удалось откатить", { description: problemOf(error, config) });
    return null;
  }
}

/** Возвращает в черновик действующую конфигурацию, ничего не публикуя. */
export async function resetDraft(discard: () => Promise<void>, data: PlatformPromptsState) {
  if (!data.published) return null;
  try {
    await discard();
    const draft = await platformPromptsApi.saveDraft(data.published.config);
    toast.success("Изменения отменены", { description: "Черновик совпадает с опубликованной версией." });
    return { ...data, draft };
  } catch (error) {
    toast.error("Не удалось отменить изменения", { description: problemOf(error, data.published.config) });
    return null;
  }
}
