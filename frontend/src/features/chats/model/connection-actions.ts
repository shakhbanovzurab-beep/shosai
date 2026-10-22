"use client";

import { toast } from "sonner";

import type { ChatConnection, ChatConnectionPatch } from "../domain/contract";
import type { SlackInstallation } from "../domain/slack-contract";
import { chatResources } from "./resources";
import { type ApiWords, describeProblem } from "./words";

/*
 * Изменения подключённых чатов: привязка и режим, возврат Leo в канал, отключение чата и пространства Slack.
 * Стирание сообщений не отменить, поэтому отключение ждёт ответа сервера, а не прячет строку заранее.
 */

const replaced = (workspaceId: string, next: ChatConnection) =>
  chatResources(workspaceId).connections.update((page) => ({
    ...page,
    items: page.items.map((item) => (item.id === next.id ? next : item)),
  }));

async function attempt<T>(ta: ApiWords, run: () => Promise<T>): Promise<T | null> {
  try {
    return await run();
  } catch (error) {
    toast.error(ta("title"), { description: describeProblem(error, ta) });
    return null;
  }
}

export async function changeChat(
  workspaceId: string,
  id: string,
  patch: ChatConnectionPatch,
  saved: string,
  ta: ApiWords,
) {
  const next = await attempt(ta, () => chatResources(workspaceId).api.patch(id, patch));
  if (next === null) return false;
  replaced(workspaceId, next);
  toast.success(saved);
  return true;
}

export async function rejoinChat(workspaceId: string, id: string, done: string, ta: ApiWords) {
  const next = await attempt(ta, () => chatResources(workspaceId).api.rejoin(id));
  if (next === null) return;
  replaced(workspaceId, next);
  toast.success(done);
}

export async function disconnectChat(workspaceId: string, connection: ChatConnection, done: string, ta: ApiWords) {
  const resources = chatResources(workspaceId);
  const removed = await attempt(ta, async () => {
    await resources.api.remove(connection.id);
    return true;
  });
  if (removed === null) return;
  resources.connections.update((page) => ({ ...page, items: page.items.filter((c) => c.id !== connection.id) }));
  void resources.installations.reload();
  toast.success(done);
}

export async function removeInstallation(workspaceId: string, item: SlackInstallation, done: string, ta: ApiWords) {
  const resources = chatResources(workspaceId);
  const removed = await attempt(ta, async () => {
    await resources.api.removeInstallation(item.id);
    return true;
  });
  if (removed === null) return;
  void resources.connections.reload();
  void resources.installations.reload();
  resources.forgetChannels();
  toast.success(done);
}
