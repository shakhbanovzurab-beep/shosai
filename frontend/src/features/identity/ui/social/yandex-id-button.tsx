import { type ReactNode, useEffect, useEffectEvent, useId, useState } from "react";

import { useLocale } from "use-intl";

import { usePreferencesStore } from "@/features/preferences/model/preferences-provider";

import { mountYandexButton } from "../../model/brand-widgets";

interface YandexIdButtonProps {
  clientId: string;
  onToken: (token: string) => void;
  fallback: ReactNode;
}

/**
 * Кнопка «Войти с Яндекс ID», нарисованная SDK Яндекса. Закрытое окно Яндекса ставит кнопку заново; если SDK не
 * загрузился, вместо неё — фирменная ссылка входа (`fallback`).
 */
export function YandexIdButton(props: YandexIdButtonProps) {
  const [round, setRound] = useState(0);
  const [failed, setFailed] = useState(false);
  if (failed) return props.fallback;
  return (
    <YandexWidget
      key={round}
      {...props}
      onCancel={() => setRound((current) => current + 1)}
      onUnavailable={() => setFailed(true)}
    />
  );
}

function YandexWidget({
  clientId,
  onToken,
  onCancel,
  onUnavailable,
}: YandexIdButtonProps & { onCancel: () => void; onUnavailable: () => void }) {
  const containerId = `yandex-id-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const theme = usePreferencesStore((state) => state.resolvedThemeMode);
  const locale = useLocale();
  const tokenArrived = useEffectEvent(onToken);
  // SDK на странице есть — человек закрыл окно: кнопка нужна снова. Нет — сервис недоступен.
  const stopped = useEffectEvent(() => ("YaAuthSuggest" in window ? onCancel() : onUnavailable()));

  useEffect(() => {
    let alive = true;
    mountYandexButton(containerId, clientId, { theme, russian: locale === "ru" })
      .then((token) => {
        if (alive) tokenArrived(token);
      })
      .catch(() => {
        if (alive) stopped();
      });
    return () => {
      alive = false;
      document.getElementById(containerId)?.replaceChildren();
    };
  }, [containerId, clientId, theme, locale]);

  return <div id={containerId} className="h-11 w-full overflow-hidden rounded-lg" />;
}
