/**
 * Сервисы быстрого входа. Набор для посетителя решает сервер (по стране — 406-ФЗ); здесь порядок кнопок и
 * названия, которые не переводятся.
 */
export const SOCIAL_PROVIDERS = ["yandex", "vk", "google", "github"] as const;

export type SocialProvider = (typeof SOCIAL_PROVIDERS)[number];

export const SOCIAL_PROVIDER_NAMES: Record<SocialProvider, string> = {
  yandex: "Yandex ID",
  vk: "VK ID",
  google: "Google",
  github: "GitHub",
};

export const isSocialProvider = (value: string): value is SocialProvider =>
  (SOCIAL_PROVIDERS as readonly string[]).includes(value);

/** В порядке кнопок и без неизвестных: старый сервер может прислать сервис, которого этот интерфейс не знает. */
export function orderedProviders(shown: readonly string[]): SocialProvider[] {
  return SOCIAL_PROVIDERS.filter((provider) => shown.includes(provider));
}

/**
 * Начало входа через сервис — переход документа на бэкенд, который уводит к сервису и возвращает на вход с
 * билетом или причиной отказа в адресе.
 */
export function socialStartUrl(provider: SocialProvider, next: string, language: string): string {
  const query = new URLSearchParams({ next, language });
  return `/v1/auth/social/${provider}/start?${query.toString()}`;
}
