import { useQuery } from "@tanstack/react-query";
import { useLocale } from "use-intl";

import { readSocialShowcase } from "../api/social-api";
import { orderedProviders, type SocialProvider } from "../domain/social-providers";

const NONE: SocialProvider[] = [];

/**
 * Сервисы быстрого входа для этого посетителя. Состав зависит от страны и за визит не меняется. Любой сбой —
 * пустая полоса, а не сломанный экран: вход по почте от этого запроса не зависит.
 */
export function useSocialProviders(): SocialProvider[] {
  const language = useLocale();
  const { data } = useQuery({
    queryKey: ["identity", "social-providers", language],
    queryFn: () => readSocialShowcase(language),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
  return data === undefined ? NONE : orderedProviders(data.providers);
}
