import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { actOnUser, readUser, searchUsers } from "../api/users-api";
import type { AccountAction, AdminUser } from "../domain/contract";
import type { UserSearch } from "../domain/search";

const USERS_KEY = ["admin", "users"] as const;
const cardKey = (id: string) => ["admin", "user", id] as const;

/** Найденные аккаунты, постранично; без запроса ничего не ищется — сервер не отдаёт список всех. */
export function useUserSearch(search: UserSearch | null) {
  const query = useInfiniteQuery({
    queryKey: [...USERS_KEY, search],
    queryFn: ({ pageParam }) => searchUsers(search as UserSearch, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
    enabled: search !== null,
  });
  const users: AdminUser[] = query.data?.pages.flatMap((page) => page.items) ?? [];
  return { ...query, users };
}

/** Карточка аккаунта. Права и состояние читаются при каждом открытии: блокировка видна сразу. */
export function useUserCard(id: string) {
  return useQuery({ queryKey: cardKey(id), queryFn: () => readUser(id) });
}

const DONE: Record<AccountAction, { title: string; description: string }> = {
  block: { title: "Аккаунт заблокирован", description: "Все сессии завершены, вход закрыт до разблокировки." },
  unblock: { title: "Аккаунт разблокирован", description: "Человек снова может войти; прежние сессии не вернутся." },
};

/** Блокировка и разблокировка: карточка заменяется ответом сервера, поиск перечитывается. */
export function useAccountAction(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ action, reasonCode }: { action: AccountAction; reasonCode: string }) =>
      actOnUser(id, action, reasonCode),
    onSuccess: (card, { action }) => {
      client.setQueryData(cardKey(id), card);
      void client.invalidateQueries({ queryKey: USERS_KEY });
      toast.success(DONE[action].title, { description: DONE[action].description });
    },
  });
}
