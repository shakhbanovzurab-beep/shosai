import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

export type EmailChallenge = components["schemas"]["EmailChallenge"];
export type EmailVerified = components["schemas"]["EmailVerified"];

export interface EmailStartForm {
  email: string;
  language: string;
  next: string;
  captchaToken: string | null;
}

/** Попросить код на почту; ответ одинаковый, есть ли у адреса аккаунт или нет (ADR 0048). */
export function startEmailSignIn({ email, language, next, captchaToken }: EmailStartForm): Promise<EmailChallenge> {
  return dataOf(
    apiClient.POST("/v1/auth/email/start", { body: { email, language, next, captcha_token: captchaToken } }),
  );
}

/** Код из письма: сессия для известного человека или билет согласий для нового. */
export function verifyEmailCode(challenge: string, code: string): Promise<EmailVerified> {
  return dataOf(apiClient.POST("/v1/auth/email/verify", { body: { challenge, code } }));
}

/** Новый код по тому же вызову; сервер отвечает, через сколько секунд можно попросить снова. */
export function resendEmailCode(challenge: string): Promise<EmailChallenge> {
  return dataOf(apiClient.POST("/v1/auth/email/resend", { body: { challenge } }));
}
