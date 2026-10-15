import { apiClient } from "@/lib/api/app-client";
import { apiErrorOf } from "@/lib/api/errors";

/**
 * Вошёл ли администратор (ADR 0049): сессию админки держит её cookie, а не вход человека. 401 — не вошёл;
 * любой другой отказ сервера уходит вызывающему как ошибка.
 */
export async function adminSignedIn(): Promise<boolean> {
  const { error, response } = await apiClient.GET("/v1/admin/session");
  if (response.ok) return true;
  if (response.status === 401) return false;
  throw apiErrorOf(response.status, error ?? null, response.headers);
}
