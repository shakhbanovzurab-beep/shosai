"use client";

import { toast } from "sonner";

import { aiModelsApi } from "../api/ai-models-api";
import type { ConnectionCheckResponse, Tier, TierDecision } from "../domain/contract";
import { problemMessage, problemText } from "../domain/problems";
import { aiModelsResource, replaceModel } from "./ai-models-store";
import { problemOf } from "./problem-description";

/** Добавляет модель из списка OpenRouter; модель приходит выключенной. Ошибку возвращает форме. */
export async function addModel(openrouterId: string, tier: Tier | null): Promise<string | null> {
  try {
    const added = await aiModelsApi.add(openrouterId.trim(), tier);
    aiModelsResource.update((data) => ({ ...data, models: [...data.models, added] }));
    toast.success("Модель добавлена", { description: "Она выключена: включите её, когда будете готовы." });
    return null;
  } catch (error) {
    return problemMessage(error);
  }
}

/** Убирает выключенную модель, которую не держит ни одна роль. */
export async function retireModel(id: string) {
  try {
    await aiModelsApi.retire(id);
    aiModelsResource.update((data) => ({ ...data, models: data.models.filter((model) => model.id !== id) }));
  } catch (error) {
    toast.error("Не удалось убрать модель", { description: problemOf(error) });
  }
}

/** Подтверждает или отклоняет уровень, который предлагает цена; списанное не пересчитывается. */
export async function decideTier(id: string, decision: TierDecision) {
  try {
    replaceModel(await aiModelsApi.decideTier(id, decision));
  } catch (error) {
    toast.error("Не удалось сохранить решение", { description: problemOf(error) });
  }
}

/** Просит сервер спросить баланс OpenRouter сейчас и перечитывает экран. */
export async function checkConnection(): Promise<ConnectionCheckResponse | null> {
  try {
    const result = await aiModelsApi.check();
    if (result.ok) toast.success("OpenRouter доступен");
    else toast.error("Подключение не работает", { description: problemText(result.code) });
    void aiModelsResource.refresh();
    return result;
  } catch (error) {
    toast.error("Не удалось проверить подключение", { description: problemOf(error) });
    return null;
  }
}
