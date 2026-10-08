"use client";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";
import { createPollingResource } from "@/lib/polling-resource";

import { aiModelsApi } from "../api/ai-models-api";
import type { AiModel, AiModelPatch, ConnectionCheckResponse } from "../domain/contract";

export const aiModelsResource = createPollingResource(aiModelsApi.list);

function applyPatch(models: AiModel[], id: string, patch: AiModelPatch): AiModel[] {
  if ("enabled" in patch)
    return models.map((model) => (model.id === id ? { ...model, enabled: patch.enabled } : model));
  return models.map((model) => ({ ...model, is_default: model.id === id }));
}

/** Shows the change at once, then keeps the server's version, or rolls back and explains why. */
export async function patchModel(id: string, patch: AiModelPatch) {
  const before = aiModelsResource.getSnapshot();
  aiModelsResource.update((data) => ({ ...data, models: applyPatch(data.models, id, patch) }));
  try {
    const saved = await aiModelsApi.patch(id, patch);
    aiModelsResource.update((data) => ({
      ...data,
      models: data.models.map((model) => {
        if (model.id === saved.id) return saved;
        return saved.is_default ? { ...model, is_default: false } : model;
      }),
    }));
  } catch (error) {
    if (before.status === "ready") aiModelsResource.update(() => before.data);
    toast.error("Не удалось сохранить", { description: apiErrorDescription(error) });
  }
}

/** Asks the server to reach OpenRouter with its key, then reloads the page data (balance included). */
export async function checkConnection(): Promise<ConnectionCheckResponse | null> {
  try {
    const result = await aiModelsApi.check();
    if (result.ok) toast.success("OpenRouter доступен", { description: result.message });
    else toast.error("Подключение не работает", { description: result.message });
    void aiModelsResource.refresh();
    return result;
  } catch (error) {
    toast.error("Не удалось проверить подключение", { description: apiErrorDescription(error) });
    return null;
  }
}
