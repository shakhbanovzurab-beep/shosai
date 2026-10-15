import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import { apiErrorOf } from "@/lib/api/errors";

/*
 * Сессия единственного администратора (ADR 0049): её держит cookie `shosai_admin` на пути /v1/admin, а не вход
 * человека, поэтому запросы идут без его токена.
 */

/** Вошёл ли администратор: 401 — нет; любой другой отказ сервера уходит вызывающему как ошибка. */
export async function adminSignedIn(): Promise<boolean> {
  const { error, response } = await apiClient.GET("/v1/admin/session");
  if (response.ok) return true;
  if (response.status === 401) return false;
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
