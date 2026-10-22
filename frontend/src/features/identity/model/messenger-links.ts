import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { messengerLinksApi } from "../api/messenger-links-api";
import type { MessengerLink, MessengerLinksResponse } from "../domain/messenger-links-contract";

/*
 * Аккаунты мессенджеров человека и подсказка о привязке (chats §1.2, CF-D4, CF-D9). Закрытие подсказки —
 * настройка аккаунта: оно сохраняется на сервере с тихими повторами, а в этой вкладке подсказка скрыта сразу и
 * остаётся скрытой, даже если сохранить так и не удалось.
 */

export const MESSENGER_LINKS_KEY = ["identity", "messenger-links"] as const;
const HINT_SAVE_RETRIES = 3;

let hintDismissedHere = false;

export const messengerLinksQuery = {
  queryKey: MESSENGER_LINKS_KEY,
  queryFn: async (): Promise<MessengerLinksResponse> => {
    const page = await messengerLinksApi.list();
    return hintDismissedHere ? { ...page, hint_dismissed: true } : page;
  },
};

export function useMessengerLinks() {
  return useQuery(messengerLinksQuery);
}

/** Скрыть подсказку в этой вкладке сразу: и кеш, и каждая следующая загрузка списка видят её закрытой. */
export function hideLinkHintHere(client: QueryClient) {
  hintDismissedHere = true;
  client.setQueryData<MessengerLinksResponse>(MESSENGER_LINKS_KEY, (page) => page && { ...page, hint_dismissed: true });
}

/** Привязанный аккаунт Telegram; у человека он один (CF-D10). */
export const telegramLinkOf = (links: readonly MessengerLink[]) =>
  links.find((link) => link.messenger === "telegram" && link.state === "linked") ?? null;

export function useDismissLinkHint() {
  const client = useQueryClient();
  const save = useMutation({
    mutationFn: messengerLinksApi.dismissHint,
    retry: HINT_SAVE_RETRIES,
    onSuccess: () => client.invalidateQueries({ queryKey: MESSENGER_LINKS_KEY, exact: true }),
  });
  return () => {
    hideLinkHintHere(client);
    save.mutate();
  };
}

/** Подтвердить предложенный аккаунт Slack, отвязать аккаунт или ответить «Это не я»; список перечитывается. */
export function useMessengerLinkActions() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: MESSENGER_LINKS_KEY, exact: true });
  const confirm = useMutation({ mutationFn: messengerLinksApi.confirm, onSettled: refresh });
  const remove = useMutation({ mutationFn: messengerLinksApi.remove, onSettled: refresh });
  return { confirm, remove };
}
