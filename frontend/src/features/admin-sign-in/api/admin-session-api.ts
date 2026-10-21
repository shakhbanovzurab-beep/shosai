import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import { apiErrorOf } from "@/lib/api/errors";
import type { components } from "@/lib/api/generated/schema";

/*
 * Сессия единственного администратора (ADR 0049): её держит cookie `shosai_admin` на пути /v1/admin, а не вход
 * человека, поэтому запросы идут без его токена.
 */

export type AdminSession = components["schemas"]["AdminSessionOut"];

/**
 * Сессия вошедшего администратора с деловым поясом платформы, или null — не вошёл (401); любой другой отказ
 * сервера уходит вызывающему как ошибка.
 */
export async function readAdminSession(): Promise<AdminSession | null> {
  const { data, error, response } = await apiClient.GET("/v1/admin/session");
  if (response.ok && data) return data;
  if (response.status === 401) return null;
  throw apiErrorOf(response.status, error ?? null, response.headers);
}

/** Войти логином и паролем; сервер ставит cookie сессии сам. */
export async function signInAdmin(username: string, password: string): Promise<void> {
  await dataOf(apiClient.POST("/v1/admin/session", { body: { username, password } }));
}

/** Выйти: сессия закрывается на сервере сразу, cookie удаляется. */
export async function signOutAdmin(): Promise<void> {
  await dataOf(apiClient.DELETE("/v1/admin/session"));
}
