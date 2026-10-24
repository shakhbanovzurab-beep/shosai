import * as React from "react";

import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";

import { type AgentScope, agentApi } from "../api/agent-api";
import type { AgentThread } from "../domain/agent-history";
import { chooseThread, messagesKey, threadsKey } from "./agent-thread";

/*
 * «Недавние чаты» пространства (ADR 0068 AG-D2): треды по активности, новыми вперёд, читаются, только когда меню
 * открыто. Выбранный тред открывается в панели; переименование и удаление идут на сервер, а удалённый текущий
 * тред оставляет панель пустой, как «Новый чат».
 */

export interface LeoThreads {
  readonly items: readonly AgentThread[];
  readonly current: string | null;
  readonly loading: boolean;
  readonly failed: boolean;
  readonly more: { readonly available: boolean; readonly loading: boolean; readonly load: () => void };
  /** Меню «Недавние чаты» открыто: список читается, только пока оно открыто. */
  readonly open: boolean;
  readonly setOpen: (open: boolean) => void;
  readonly select: (threadId: string) => void;
  readonly rename: (threadId: string, title: string) => Promise<void>;
  readonly remove: (threadId: string) => Promise<void>;
}

const listKey = (scope: string) => ["agent", "threads", "list", scope] as const;

export function useAgentThreads(scopeKey: string, scope: AgentScope, current: string | null): LeoThreads {
  const queryClient = useQueryClient();
  const [open, setOpen] = React.useState(false);
  const list = useInfiniteQuery({
    queryKey: listKey(scopeKey),
    queryFn: ({ pageParam }) => agentApi.threads(scope, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
    enabled: open,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: listKey(scopeKey) });
    void queryClient.invalidateQueries({ queryKey: threadsKey(scopeKey) });
  };

  return {
    items: list.data?.pages.flatMap((page) => page.items) ?? [],
    current,
    loading: list.isPending && open,
    failed: list.isError,
    more: { available: list.hasNextPage, loading: list.isFetchingNextPage, load: () => void list.fetchNextPage() },
    open,
    setOpen,
    select: (threadId) => {
      chooseThread(scopeKey, threadId);
      setOpen(false);
    },
    rename: async (threadId, title) => {
      await agentApi.rename(threadId, title);
      refresh();
    },
    remove: async (threadId) => {
      await agentApi.remove(threadId);
      if (threadId === current) chooseThread(scopeKey, null);
      queryClient.removeQueries({ queryKey: messagesKey(threadId) });
      refresh();
    },
  };
}
