"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { chatsApi } from "../api/chats-api";
import type { ConnectStatus } from "../domain/telegram-contract";

/*
 * Ресурсы командных чатов, по набору на пространство: настройки и подключения грузятся при первом подписчике.
 * Статус кода Telegram опрашивается, пока код ждёт группу и окно открыто; как только группа подключилась,
 * список подключений перечитывается.
 */

const isWaiting = (status: ConnectStatus) => status.status === "pending";

/**
 * Код, за которым больше никто не следит (окно закрыли, пока он ждал группу), отменяется: он не должен
 * подключить группу без человека. Отмена — на следующем такте, чтобы переподписка того же экрана её не вызвала;
 * её отказ ничего не меняет — код и так истечёт через 30 минут.
 */
function cancelledWhenUnwatched(resource: PollingResource<ConnectStatus>, cancel: () => Promise<void>) {
  let watchers = 0;
  const waiting = () => {
    const state = resource.getSnapshot();
    return state.status !== "ready" || isWaiting(state.data);
  };
  return {
    ...resource,
    subscribe(listener: () => void) {
      watchers++;
      const unsubscribe = resource.subscribe(listener);
      return () => {
        unsubscribe();
        watchers--;
        setTimeout(() => {
          if (watchers === 0 && waiting()) cancel().catch(() => undefined);
        }, 0);
      };
    },
  };
}

function createChatResources(workspaceId: string) {
  const api = chatsApi(workspaceId);
  const connections = createPollingResource(api.list);
  const codes = new Map<string, PollingResource<ConnectStatus>>();
  return {
    api,
    settings: createPollingResource(api.settings),
    connections,
    code(id: string) {
      let resource = codes.get(id);
      if (!resource) {
        const poll = async () => {
          const status = await api.pollCode(id);
          if (status.status === "connected") void connections.reload();
          return status;
        };
        resource = cancelledWhenUnwatched(createPollingResource(poll, isWaiting), () => api.cancelCode(id));
        codes.set(id, resource);
      }
      return resource;
    },
  };
}

export type ChatResources = ReturnType<typeof createChatResources>;

const cache = new Map<string, ChatResources>();

/** Ресурсы одного пространства, созданные при первом обращении. */
export function chatResources(workspaceId: string): ChatResources {
  let resources = cache.get(workspaceId);
  if (!resources) {
    resources = createChatResources(workspaceId);
    cache.set(workspaceId, resources);
  }
  return resources;
}

export const useChatSettings = (workspaceId: string) => usePollingResource(chatResources(workspaceId).settings);
export const useConnections = (workspaceId: string) => usePollingResource(chatResources(workspaceId).connections);
export const useCodeStatus = (workspaceId: string, codeId: string) =>
  usePollingResource(chatResources(workspaceId).code(codeId));
