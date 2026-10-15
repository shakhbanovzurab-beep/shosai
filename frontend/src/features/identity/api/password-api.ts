import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

/** Задать новый пароль по ссылке из письма; сервер закрывает остальные сессии аккаунта. */
export async function resetPassword(token: string, password: string): Promise<void> {
  await dataOf(apiClient.POST("/v1/auth/password/reset", { body: { token, password } }));
}
