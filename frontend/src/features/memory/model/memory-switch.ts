"use client";

import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { apiErrorDescription } from "@/lib/api/error-description";
import { createPollingResource } from "@/lib/polling-resource";

import { memoryApi } from "../api/memory-api";

/*
 * Переключатель памяти на `/v1/agent/memory/settings`: выключенная память не читается и не пишется, но ничего не
 * удаляет. Переключение видно сразу; отказ сервера возвращает прежнее положение.
 */

export const memorySwitch = createPollingResource<boolean>(memoryApi.enabled);

export const useMemorySwitch = () => usePollingResource(memorySwitch);

export async function turnMemory(enabled: boolean, failedTitle: string) {
  memorySwitch.update(() => enabled);
  try {
    const saved = await memoryApi.setEnabled(enabled);
    memorySwitch.update(() => saved);
  } catch (error) {
    memorySwitch.update(() => !enabled);
    toast.error(failedTitle, { description: apiErrorDescription(error) });
  }
}
