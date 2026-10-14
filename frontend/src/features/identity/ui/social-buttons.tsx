import { siGithub, siGoogle, siVk } from "simple-icons";
import { useLocale, useTranslations } from "use-intl";

import { SimpleIcon } from "@/components/simple-icon";
import { Button } from "@/components/ui/button";

import { SOCIAL_PROVIDER_NAMES, type SocialProvider, socialStartUrl } from "../domain/social-providers";
import { useSocialProviders } from "../model/social-showcase";

const MARKS = { vk: siVk, google: siGoogle, github: siGithub } as const;

function ProviderMark({ provider }: { provider: SocialProvider }) {
  if (provider === "yandex") {
    return (
      <span
        aria-hidden="true"
        className="grid size-4 place-items-center rounded-full bg-red-600 font-bold text-[0.625rem] text-white"
      >
        {/* i18n-ignore: буква знака Яндекса, не текст интерфейса */}Я
      </span>
    );
  }
  return <SimpleIcon icon={MARKS[provider]} aria-hidden="true" className="size-4" />;
}

/**
 * Быстрый вход: переход документа к сервису через бэкенд, а не запрос — сервис показывает свою страницу согласия.
 * Под формой, а не над ней: почта с паролем остаётся основным способом. Первый вход заводит аккаунт после
 * экрана согласий, поэтому отдельной кнопки «зарегистрироваться через» нет.
 */
export function SocialButtons({ next }: { next: string }) {
  const t = useTranslations("identity");
  const language = useLocale();
  const providers = useSocialProviders();
  if (providers.length === 0) return null;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3 text-muted-foreground text-xs">
        <span aria-hidden="true" className="h-px flex-1 bg-border" />
        {t("screen.or")}
        <span aria-hidden="true" className="h-px flex-1 bg-border" />
      </div>
      <div className="flex flex-col gap-2">
        {providers.map((provider) => (
          <Button key={provider} variant="outline" asChild>
            <a href={socialStartUrl(provider, next, language)}>
              <ProviderMark provider={provider} />
              {t("social.continueWith", { provider: SOCIAL_PROVIDER_NAMES[provider] })}
            </a>
          </Button>
        ))}
      </div>
    </div>
  );
}
