import * as React from "react";

import { type InfiniteData, useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { type AgentScope, agentApi } from "../api/agent-api";
import { type AgentMessage, type AgentPage, conversationOf } from "../domain/agent-history";
import type { LeoContext } from "../domain/context";

/*
 * Тред пространства и его история (AG-D2): панель открывает последний тред пространства по активности, «Новый
 * чат» её опустошает, а тред создаётся с первым вопросом. В браузере ничего из разговора не хранится: после
 * перезагрузки и на другом устройстве история та же — с сервера.
 */

// Вопрос без ответа, младше этого, — ход ещё идёт где-то ещё: история перечитывается, пока он не закончится.
const ANSWER_WAIT_MS = 4 * 60_000;
const ANSWER_POLL_MS = 3_000;

type History = InfiniteData<AgentPage<AgentMessage>, string | null>;

const chosen = new Map<string, string | null>();
const listeners = new Set<() => void>();

/** Тред, выбранный в пространстве: id, null — новый чат, undefined — последний по активности. */
export const chosenThread = (scope: string): string | null | undefined => chosen.get(scope);

export function chooseThread(scope: string, threadId: string | null) {
  chosen.set(scope, threadId);
  for (const listener of listeners) listener();
}

function subscribeChosen(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function scopeOf(context: LeoContext): AgentScope {
  return context.kind === "workspace" ? { kind: "workspace", workspace_id: context.id } : { kind: "personal" };
}

/** Списки тредов всех пространств: последняя активность треда меняет порядок в каждом. */
export const allThreadsKey = ["agent", "threads"] as const;
export const threadsKey = (scope: string) => [...allThreadsKey, scope] as const;
export const messagesKey = (threadId: string | null) => ["agent", "messages", threadId] as const;

function waitsForAnswer(data: History | undefined): boolean {
  const newest = data?.pages[0]?.items[0];
  return newest?.role === "user" && Date.now() - Date.parse(newest.created_at) < ANSWER_WAIT_MS;
}

/** Тред пространства и разговор в нём, старыми вперёд; `idle` — ход не идёт в этой панели. */
export function useAgentThread(scopeKey: string, scope: AgentScope, idle: boolean) {
  const picked = React.useSyncExternalStore(
    subscribeChosen,
    () => chosenThread(scopeKey),
    () => undefined,
  );
  const latest = useQuery({
    queryKey: threadsKey(scopeKey),
    queryFn: () => agentApi.latestThread(scope),
    enabled: picked === undefined,
  });
  // null выбранного треда — новый чат, а не «нет выбора»: последний тред подставляется только без выбора.
  let threadId: string | null = latest.data?.id ?? null;
  if (picked !== undefined) threadId = picked;
  const history = useInfiniteQuery({
    queryKey: messagesKey(threadId),
    queryFn: ({ pageParam }) => agentApi.messages(threadId ?? "", pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
    enabled: threadId !== null,
    refetchInterval: (query) => (idle && waitsForAnswer(query.state.data) ? ANSWER_POLL_MS : false),
  });
  return {
    threadId,
    loading: latest.isPending && picked === undefined,
    conversation: threadId === null ? [] : conversationOf(history.data?.pages ?? []),
    earlier: {
      available: history.hasNextPage,
      loading: history.isFetchingNextPage,
      load: () => void history.fetchNextPage(),
    },
  };
}
