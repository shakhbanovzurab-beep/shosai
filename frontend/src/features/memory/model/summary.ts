"use client";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";
import { createPollingResource } from "@/lib/polling-resource";
import { inDomain } from "@/lib/resource-domains";

import { memoryApi } from "../api/memory-api";
import { summaryApi } from "../api/summary-api";
import type { MemoryChange, MemoryMessageReply, MemorySummary } from "../domain/summary-contract";
import { factsResource } from "./facts-resource";

/*
 * Сводка памяти в Настройках › Память. После сообщения сервер переписывает её в фоне: показанная сводка
 * перечитывается, пока она устаревшая, но не дольше двух минут — дальше её обновит открытие или «Обновить».
 */

const AWAIT_REWRITE_MS = 120_000;
let awaitUntil = 0;

export const summaryResource = inDomain(
  "memory",
  createPollingResource<MemorySummary>(summaryApi.get, (summary) => summary.stale && Date.now() < awaitUntil),
);

function failed(error: unknown, title: string) {
  toast.error(title, { description: apiErrorDescription(error) });
}

/** Вопрос или изменение; ответ, или null, когда сервер отказал (тост говорит почему). */
export async function sendSummaryMessage(
  message: string,
  key: string,
  failedTitle: string,
): Promise<MemoryMessageReply | null> {
  try {
    const reply = await summaryApi.send(message, key);
    awaitUntil = Date.now() + AWAIT_REWRITE_MS;
    summaryResource.update(() => reply.summary);
    if (reply.changes.length > 0) void factsResource.reload();
    return reply;
  } catch (error) {
    failed(error, failedTitle);
    return null;
  }
}

/** Переписать сводку сейчас. */
export async function refreshSummary(failedTitle: string) {
  try {
    const summary = await summaryApi.refresh();
    summaryResource.update(() => summary);
  } catch (error) {
    failed(error, failedTitle);
  }
}

/**
 * Отменить изменение из ответа: запомненное забывается, исправленное и забытое возвращаются (сервер хранит их
 * сутки). true — отменено.
 */
export async function undoChange(change: MemoryChange, failedTitle: string): Promise<boolean> {
  try {
    if (change.change === "remembered") await memoryApi.forget(change.fact.id);
    else await memoryApi.restore(change.replaced_id ?? change.fact.id);
  } catch (error) {
    failed(error, failedTitle);
    return false;
  }
  void factsResource.reload();
  void summaryResource.reload();
  return true;
}
