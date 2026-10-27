"use client";

import { toast } from "sonner";

import { createPollingResource } from "@/lib/polling-resource";

import { aiModelsApi } from "../api/ai-models-api";
import type { AiModel, AiModelsResponse, ModelRole, RoleDefault } from "../domain/contract";
import { problemOf } from "./problem-description";

export const aiModelsResource = createPollingResource(aiModelsApi.list);

/** Модель Leo по умолчанию отмечена у строк каталога. */
function withDefaults(data: AiModelsResponse, defaults: RoleDefault[]): AiModelsResponse {
  const leo = defaults.find((item) => item.role === "leo")?.model_id;
  return { ...data, defaults, models: data.models.map((model) => ({ ...model, is_default: model.id === leo })) };
}

/** Строка каталога после её изменения на сервере. */
export function replaceModel(saved: AiModel) {
  aiModelsResource.update((data) => ({
    ...data,
    models: data.models.map((model) => (model.id === saved.id ? saved : model)),
  }));
}

/** Показывает изменение сразу и откатывает его с объяснением, если сервер отказал. */
async function optimistic(change: (data: AiModelsResponse) => AiModelsResponse, save: () => Promise<void>) {
  const before = aiModelsResource.getSnapshot();
  aiModelsResource.update(change);
  try {
    await save();
  } catch (error) {
    if (before.status === "ready") aiModelsResource.update(() => before.data);
    toast.error("Не удалось сохранить", { description: problemOf(error) });
  }
}

export function switchModel(id: string, enabled: boolean) {
  return optimistic(
    (data) => ({ ...data, models: data.models.map((model) => (model.id === id ? { ...model, enabled } : model)) }),
    async () => replaceModel(await aiModelsApi.switch(id, enabled)),
  );
}

export function setRoleDefault(role: ModelRole, modelId: string, fallbackId: string | null) {
  const chosen: RoleDefault = { role, model_id: modelId, fallback_model_id: fallbackId };
  const place = (defaults: RoleDefault[], item: RoleDefault) => [
    ...defaults.filter((other) => other.role !== item.role),
    item,
  ];
  return optimistic(
    (data) => withDefaults(data, place(data.defaults, chosen)),
    async () => {
      const saved = await aiModelsApi.setDefault(role, modelId, fallbackId);
      aiModelsResource.update((data) => withDefaults(data, place(data.defaults, saved)));
    },
  );
}
