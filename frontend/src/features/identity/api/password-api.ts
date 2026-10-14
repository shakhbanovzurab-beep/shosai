import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

/** Попросить ссылку для нового пароля. Ответ один и тот же, есть аккаунт у адреса или нет. */
export async function requestPasswordReset(email: string, captchaToken: string | null): Promise<void> {
  await dataOf(apiClient.POST("/v1/auth/password/forgot", { body: { email, captcha_token: captchaToken } }));
}

/** Задать новый пароль по ссылке из письма; сервер закрывает остальные сессии аккаунта. */
export async function resetPassword(token: string, password: string): Promise<void> {
  await dataOf(apiClient.POST("/v1/auth/password/reset", { body: { token, password } }));
}
