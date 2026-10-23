import { type ReactNode, useEffect, useEffectEvent, useId, useState } from "react";

import { useLocale } from "use-intl";

import { usePreferencesStore } from "@/features/preferences/model/preferences-provider";

import { mountYandexButton, YandexIdUnavailableError } from "../../model/brand-widgets";

interface YandexIdButtonProps {
  clientId: string;
  onToken: (token: string) => void;
  fallback: ReactNode;
}

/**
 * Кнопка «Войти с Яндекс ID», нарисованная SDK Яндекса. Пока SDK грузится (это секунды), на её месте —
 * фирменная ссылка входа (`fallback`), а не пустое место; она же остаётся, если SDK не загрузился. Закрытое
 * окно Яндекса ставит кнопку заново.
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
  fallback,
  onCancel,
  onUnavailable,
}: YandexIdButtonProps & { onCancel: () => void; onUnavailable: () => void }) {
  const [shown, setShown] = useState(false);
  const containerId = `yandex-id-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const theme = usePreferencesStore((state) => state.resolvedThemeMode);
  const locale = useLocale();
  const tokenArrived = useEffectEvent(onToken);
  // SDK не поставил кнопку — она не появится до перезагрузки, остаётся ссылка. Иначе окно Яндекса закрылось без
  // входа, SDK убрал свой фрейм, и кнопка нужна снова.
  const stopped = useEffectEvent((error: unknown) =>
    error instanceof YandexIdUnavailableError ? onUnavailable() : onCancel(),
  );

  useEffect(() => {
    let alive = true;
    mountYandexButton(containerId, clientId, { theme, russian: locale === "ru" }, () => {
      if (alive) setShown(true);
    })
      .then((token) => {
        if (alive) tokenArrived(token);
      })
      .catch((error: unknown) => {
        if (alive) stopped(error);
      });
    return () => {
      alive = false;
      document.getElementById(containerId)?.replaceChildren();
    };
  }, [containerId, clientId, theme, locale]);

  // Кнопка SDK рисуется под ссылкой и открывается, когда готова: ни пустого места, ни скачка высоты. Пока она под
  // ссылкой, inert убирает её фрейм из фокуса и дерева доступности.
  return (
    // isolate: SDK ставит своему фрейму z-index, и без своего слоя наложения он перекрывал бы меню страницы.
    <div className="relative isolate h-11 w-full">
      <div id={containerId} className="h-11 w-full overflow-hidden rounded-lg" inert={!shown} />
      {shown ? null : <div className="absolute inset-0">{fallback}</div>}
    </div>
  );
}
