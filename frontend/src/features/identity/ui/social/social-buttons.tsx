import { useEffect, useTransition } from "react";

import { preconnect } from "react-dom";
import { useLocale, useTranslations } from "use-intl";

import type { SocialProvider } from "../../domain/social-providers";
import { preloadYandexSdk } from "../../model/brand-widgets";
import type { Outcome } from "../../model/outcome";
import { type Arrival, arriveByVkCode, arriveByWidget } from "../../model/passwordless";
import { useSocialShowcase } from "../../model/social-showcase";
import { BrandLinkButton } from "./brand-link-button";
import { GoogleButton } from "./google-button";
import { VkIdButton } from "./vk-id-button";
import { YandexIdButton } from "./yandex-id-button";

/**
 * Быстрый вход: набор сервисов выбирает сервер (Яндекс и VK — для России и русского интерфейса, Google и GitHub —
 * остальным; ADR 0048). Яндекс, Google и VK ID — их собственные виджеты, GitHub — фирменная ссылка.
 */
export function SocialButtons({
  next,
  onArrival,
}: {
  next: string;
  onArrival: (outcome: Outcome<Arrival>, provider: "yandex" | "google" | "vk") => void;
}) {
  const t = useTranslations("identity");
  const language = useLocale();
  const { providers, yandexClientId, googleClientId, vkClientId } = useSocialShowcase();
  const [pending, startTransition] = useTransition();
  const russian = language === "ru";
  // На русском экране почти наверняка будет кнопка Яндекса: соединения и SDK — сразу, не после списка
  // провайдеров. Цепочка загрузок SDK длинная, и так кнопка появляется на полсекунды раньше.
  if (russian) {
    preconnect("https://yastatic.net");
    preconnect("https://autofill.yandex.ru");
  }
  useEffect(() => {
    if (russian) preloadYandexSdk();
  }, [russian]);
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
    // ID приложения VK ID — число; иное значение (например, ключ вместо ID) виджет не запустит.
    const vkApp = Number(vkClientId);
    if (provider === "vk" && Number.isSafeInteger(vkApp) && vkApp > 0) {
      return (
        <VkIdButton
          appId={vkApp}
          next={next}
          onCode={(answer) => startTransition(async () => onArrival(await arriveByVkCode(answer), "vk"))}
          fallback={fallback}
        />
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
