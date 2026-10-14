import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { LanguageCode } from "@/lib/language";

import type { Me, Tokens } from "../domain/session";

const CSRF_HEADER = "X-CSRF-Token";

export interface Credentials {
  email: string;
  password: string;
  captchaToken: string | null;
}

/** Вход паролем; refresh приходит в httpOnly cookie, CSRF — в cookie, доступной странице. */
export function signInWithPassword({ email, password, captchaToken }: Credentials): Promise<Tokens> {
  return dataOf(apiClient.POST("/v1/auth/login", { body: { email, password, captcha_token: captchaToken } }));
}

/** Новый токен доступа по refresh-cookie; CSRF-значение — из cookie этой же сессии, если она есть. */
export function refreshSession(csrf: string | null): Promise<Tokens> {
  const headers = csrf === null ? {} : { [CSRF_HEADER]: csrf };
  return dataOf(apiClient.POST("/v1/auth/refresh", { headers }));
}

/** Закончить сессию этого устройства на сервере. */
export async function endSession(csrf: string | null): Promise<void> {
  const headers = csrf === null ? {} : { [CSRF_HEADER]: csrf };
  await dataOf(apiClient.POST("/v1/auth/logout", { headers }));
}

/** Вошедший человек: профиль, согласия, роли оператора. */
export function readMe(): Promise<Me> {
  return dataOf(apiClient.GET("/v1/me"));
}

/** Сохранить язык интерфейса в профиле: письма и другие устройства говорят на нём же. */
export function saveLanguage(language: LanguageCode): Promise<Me> {
  // Смена языка ничего не отзывает: предупреждение об отзыве согласия здесь не нужно.
  return dataOf(apiClient.PATCH("/v1/me", { body: { language, cross_border_warning_confirmed: false } }));
}
