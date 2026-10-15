import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type { AccountAction, AdminUserCard, UsersPage } from "../domain/contract";
import type { UserSearch } from "../domain/search";

const PAGE_SIZE = 25;

/** Поиск по точной почте (один дом из каталога) или по части имени в обоих домах, новые аккаунты первыми. */
export function searchUsers(search: UserSearch, cursor: string | null): Promise<UsersPage> {
  return dataOf(apiClient.GET("/v1/admin/users", { params: { query: { ...search, cursor, limit: PAGE_SIZE } } }));
}

/** Карточка: профиль, состояние, сессии, входы и расходы на ИИ. */
export function readUser(id: string): Promise<AdminUserCard> {
  return dataOf(apiClient.GET("/v1/admin/users/{user_id}", { params: { path: { user_id: id } } }));
}

/** Заблокировать или разблокировать; ответ — карточка после действия, в журнале аудита — одна запись. */
export function actOnUser(id: string, action: AccountAction, reasonCode: string): Promise<AdminUserCard> {
  const params = { path: { user_id: id } };
  const body = { reason_code: reasonCode };
  return dataOf(
    action === "block"
      ? apiClient.POST("/v1/admin/users/{user_id}/block", { params, body })
      : apiClient.POST("/v1/admin/users/{user_id}/unblock", { params, body }),
  );
}
