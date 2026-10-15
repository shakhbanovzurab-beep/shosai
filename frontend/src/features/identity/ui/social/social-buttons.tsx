import { useTransition } from "react";

import { useLocale, useTranslations } from "use-intl";

import type { SocialProvider } from "../../domain/social-providers";
import type { Outcome } from "../../model/outcome";
import { type Arrival, arriveByWidget } from "../../model/passwordless";
import { useSocialShowcase } from "../../model/social-showcase";
import { BrandLinkButton } from "./brand-link-button";
import { GoogleButton } from "./google-button";
import { YandexIdButton } from "./yandex-id-button";

/**
 * Быстрый вход: набор сервисов выбирает сервер по стране посетителя (Яндекс и VK в России, Google и GitHub в
 * остальном мире; 406-ФЗ). Яндекс и Google — их собственные виджеты, VK ID и GitHub — фирменные ссылки.
 */
export function SocialButtons({
  next,
  onArrival,
}: {
  next: string;
  onArrival: (outcome: Outcome<Arrival>, provider: "yandex" | "google") => void;
}) {
  const t = useTranslations("identity");
  const language = useLocale();
  const { providers, yandexClientId, googleClientId } = useSocialShowcase();
  const [pending, startTransition] = useTransition();
  if (providers.length === 0) return null;

  const arrive = (provider: "yandex" | "google", token: string) => {
    startTransition(async () => onArrival(await arriveByWidget(provider, token, next, language), provider));
  };
  const button = (provider: SocialProvider) => {
    const fallback = <BrandLinkButton provider={provider} next={next} />;
    if (provider === "yandex" && yandexClientId) {
      return (
        <YandexIdButton clientId={yandexClientId} onToken={(token) => arrive("yandex", token)} fallback={fallback} />
      );
    }
    if (provider === "google" && googleClientId) {
      return (
        <GoogleButton clientId={googleClientId} onToken={(token) => arrive("google", token)} fallback={fallback} />
      );
    }
    return fallback;
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2.5" aria-busy={pending}>
        {providers.map((provider) => (
          <div key={provider}>{button(provider)}</div>
        ))}
      </div>
      {/* Разделитель — только под кнопками сервисов: без них почта и так единственный путь. */}
      <div className="flex items-center gap-3 text-muted-foreground text-sm">
        <span aria-hidden="true" className="h-px flex-1 bg-border" />
        {t("signIn.orEmail")}
        <span aria-hidden="true" className="h-px flex-1 bg-border" />
      </div>
    </div>
  );
}
