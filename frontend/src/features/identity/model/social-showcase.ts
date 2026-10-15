import { useQuery } from "@tanstack/react-query";
import { useLocale } from "use-intl";

import { readSocialShowcase } from "../api/social-api";
import { orderedProviders, type SocialProvider } from "../domain/social-providers";

/** Сервисы для посетителя и то, что нужно их фирменным виджетам. */
export interface SocialShowcase {
  providers: SocialProvider[];
  yandexClientId: string | null;
  googleClientId: string | null;
}

const NONE: SocialShowcase = { providers: [], yandexClientId: null, googleClientId: null };

/**
 * Сервисы быстрого входа для этого посетителя. Состав зависит от страны и за визит не меняется. Любой сбой —
 * пустая полоса, а не сломанный экран: вход по почте от этого запроса не зависит.
 */
export function useSocialShowcase(): SocialShowcase {
  const language = useLocale();
  const { data } = useQuery({
    queryKey: ["identity", "social-providers", language],
    queryFn: () => readSocialShowcase(language),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
  if (data === undefined) return NONE;
  return {
    providers: orderedProviders(data.providers),
    yandexClientId: data.yandex_client_id,
    googleClientId: data.google_client_id,
  };
}
