"use client";

import { toast } from "sonner";

import type { RetentionDays } from "../domain/contract";
import type { ConnectCodeCreate } from "../domain/telegram-contract";
import { chatResources } from "./resources";
import { type ApiWords, describeProblem } from "./words";

/*
 * Действия над командными чатами пространства. Каждое сообщает об успехе или отказе тостом, словами
 * кабинета, и возвращает итог, по которому экран решает, что показать дальше.
 */

/** Новый срок хранения сообщений; `saved` — слова тоста об успехе. */
export async function setRetention(workspaceId: string, days: RetentionDays, saved: string, ta: ApiWords) {
  const { api, settings } = chatResources(workspaceId);
  try {
    const next = await api.patchSettings({ retention_days: days });
    settings.update(() => next);
    toast.success(saved);
    return true;
  } catch (error) {
    toast.error(ta("title"), { description: describeProblem(error, ta) });
    return false;
  }
}

/** Код подключения группы Telegram; null — отказ, о котором уже сказано. */
export async function requestCode(workspaceId: string, body: ConnectCodeCreate, ta: ApiWords) {
  try {
    return await chatResources(workspaceId).api.createCode(body);
  } catch (error) {
    toast.error(ta("title"), { description: describeProblem(error, ta) });
    return null;
  }
}
