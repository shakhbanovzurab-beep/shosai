import { useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api/errors";

import { messengerLinksApi } from "../api/messenger-links-api";
import type { LinkRequest } from "../domain/messenger-links-contract";
import { MESSENGER_LINKS_KEY } from "./messenger-links";

/*
 * Привязка Telegram по глубокой ссылке (chats §1.2): Telegram открывается прямо по нажатию — браузеры блокируют
 * вкладки, открытые позже, — и получает ссылку, как только её вернёт сервер. Запрос опрашивается каждые 2 с,
 * пока вкладка видна, и сразу, когда человек возвращается из Telegram.
 */

const POLL_MS = 2_000;
const requestKey = (id: string | null) => ["identity", "telegram-link-request", id] as const;
const isPending = (request: LinkRequest | undefined) => request?.status === "pending";

export type TelegramLinkFlow =
  | { step: "idle" | "starting" }
  | { step: "waiting"; url: string; bot: string }
  | { step: "linked"; handle: string }
  | { step: "expired" | "refused" };

/** Бот из ссылки `https://t.me/<bot>?start=<token>`: в его чате человек нажимает Start. */
const botOf = (url: string) => new URL(url).pathname.slice(1);

function flowOf(starting: boolean, request: LinkRequest | undefined): TelegramLinkFlow {
  if (starting) return { step: "starting" };
  if (!request) return { step: "idle" };
  if (request.status === "pending") return { step: "waiting", url: request.url, bot: botOf(request.url) };
  if (request.status === "linked")
    return { step: "linked", handle: request.link?.account.handle ?? request.link?.account.name ?? "" };
  return { step: request.status };
}

export function useTelegramLink(onStartFailed: (error: unknown) => void) {
  const client = useQueryClient();
  const [requestId, setRequestId] = useState<string | null>(null);
  const request = useQuery({
    queryKey: requestKey(requestId),
    queryFn: async () => {
      const next = await messengerLinksApi.request(requestId ?? "");
      if (next.status === "linked") await client.invalidateQueries({ queryKey: MESSENGER_LINKS_KEY, exact: true });
      return next;
    },
    enabled: requestId !== null,
    staleTime: 0,
    refetchInterval: (query) => (isPending(query.state.data) ? POLL_MS : false),
    refetchOnWindowFocus: (query) => isPending(query.state.data),
  });
  // Список перечитывается и после отказа: Telegram могли привязать в другой вкладке (409 messenger_already_linked).
  const start = useMutation({
    mutationFn: messengerLinksApi.startTelegram,
    onSettled: () => client.invalidateQueries({ queryKey: MESSENGER_LINKS_KEY, exact: true }),
  });

  const begin = () => {
    const tab = window.open("", "_blank");
    if (tab) tab.opener = null;
    start.mutate(undefined, {
      onSuccess: (created) => {
        if (tab) tab.location.href = created.url;
        client.setQueryData(requestKey(created.id), created);
        setRequestId(created.id);
      },
      onError: (error) => {
        tab?.close();
        if (!(error instanceof ApiError && error.code === "messenger_already_linked")) onStartFailed(error);
      },
    });
  };

  /** Перестать ждать: ссылка сама истечёт через 10 минут. */
  const reset = () => setRequestId(null);

  return { flow: flowOf(start.isPending, requestId === null ? undefined : request.data), begin, reset };
}
