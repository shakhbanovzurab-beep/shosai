import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

export type SocialShowcase = components["schemas"]["ProvidersAnswer"];
export type SocialSession = components["schemas"]["SocialSession"];
export type SocialConsents = components["schemas"]["Consents-Input"];
export type SocialTickets = components["schemas"]["SocialTickets"];

/** Сервисы быстрого входа для этого посетителя; их набор зависит от страны (406-ФЗ). */
export function readSocialShowcase(language: string): Promise<SocialShowcase> {
  return dataOf(apiClient.GET("/v1/auth/social/providers", { params: { query: { language } } }));
}

/** Обменять одноразовый билет из адреса на сессию. */
export function completeSocialSignIn(ticket: string): Promise<SocialSession> {
  return dataOf(apiClient.POST("/v1/auth/social/complete", { body: { ticket } }));
}

export interface SocialRegistration {
  ticket: string;
  country: string;
  language: string;
  consents: SocialConsents;
  // Пояс браузера; незнакомый серверу он отбрасывает, регистрацию это не отклоняет.
  timezone: string;
}

/** Первый вход через сервис: завести аккаунт с отмеченными согласиями и открыть сессию. */
export function registerWithSocial(registration: SocialRegistration): Promise<SocialSession> {
  return dataOf(apiClient.POST("/v1/auth/social/register", { body: registration }));
}

/** Токен фирменного виджета Яндекса или Google — сервер сверяет его у провайдера и отдаёт билет. */
export function exchangeWidgetToken(
  provider: "yandex" | "google",
  token: string,
  next: string,
  language: string,
): Promise<SocialTickets> {
  return dataOf(
    apiClient.POST("/v1/auth/social/{provider}/widget-token", {
      params: { path: { provider } },
      body: { token, next, language },
    }),
  );
}

export type VkWidgetFlow = components["schemas"]["WidgetStart"];

/** Начать вход через VK ID OneTap: сервер хранит verifier PKCE, виджет получает state и хеш. */
export function startVkWidget(next: string, language: string): Promise<VkWidgetFlow> {
  return dataOf(
    apiClient.POST("/v1/auth/social/{provider}/widget-start", {
      params: { path: { provider: "vk" } },
      body: { next, language },
    }),
  );
}

/** Код, state и device_id, которые отдал OneTap: сервер меняет код у VK ID и отдаёт билет. */
export function exchangeVkCode(code: string, state: string, deviceId: string): Promise<SocialTickets> {
  return dataOf(
    apiClient.POST("/v1/auth/social/{provider}/widget-code", {
      params: { path: { provider: "vk" } },
      body: { code, state, device_id: deviceId },
    }),
  );
}
