"use client";

import { toast } from "sonner";

import { ApiError } from "@/lib/api/errors";

import type { RetentionDays } from "../domain/contract";
import type { SlackChannel, SlackConnect } from "../domain/slack-contract";
import type { ConnectCodeCreate } from "../domain/telegram-contract";
import { chatResources } from "./resources";
import { type ApiWords, type ConnectWords, describeProblem } from "./words";

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

/** Каналы Slack пачкой: все или ни одного; уже подключённые отказ называет по именам. */
export async function connectChannels(
  workspaceId: string,
  body: SlackConnect,
  picked: readonly SlackChannel[],
  words: { t: ConnectWords; ta: ApiWords },
) {
  const resources = chatResources(workspaceId);
  try {
    const { items } = await resources.api.connectSlack(body);
    void resources.connections.reload();
    void resources.installations.reload();
    resources.forgetChannels();
    toast.success(words.t("slack.connected", { count: items.length }));
    return true;
  } catch (error) {
    const taken =
      error instanceof ApiError && error.code === "channel_already_connected" ? error.params.channel_ids : null;
    const takenIds = new Set(Array.isArray(taken) ? taken : []);
    const names = picked.filter((c) => takenIds.has(c.id)).map((c) => `#${c.name}`);
    const description =
      names.length > 0
        ? words.t("slack.alreadyConnected", { channels: names.join(", ") })
        : describeProblem(error, words.ta);
    toast.error(words.ta("title"), { description });
    return false;
  }
}
