import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

export type RegistrationForm = components["schemas"]["RegistrationRequest"];
export type RegistrationStarted = components["schemas"]["RegistrationStartedResponse"];
export type AccountCreated = components["schemas"]["AccountCreatedResponse"];

/** Начать регистрацию: сервер отправляет на почту код из шести цифр; аккаунт появится после кода. */
export function startRegistration(form: RegistrationForm): Promise<RegistrationStarted> {
  return dataOf(apiClient.POST("/v1/auth/register", { body: form }));
}

/** Подтвердить почту кодом: сервер заводит аккаунт и сразу открывает сессию. */
export function verifyRegistration(registrationId: string, code: string): Promise<AccountCreated> {
  return dataOf(apiClient.POST("/v1/auth/register/verify", { body: { registration_id: registrationId, code } }));
}

/** Отправить код ещё раз; сервер отвечает, через сколько секунд можно будет попросить снова. */
export function resendRegistrationCode(registrationId: string): Promise<RegistrationStarted> {
  return dataOf(apiClient.POST("/v1/auth/register/resend", { body: { registration_id: registrationId } }));
}
