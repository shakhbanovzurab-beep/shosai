import { type CSSProperties, type ReactNode, useEffect, useEffectEvent, useRef, useState } from "react";

import { useLocale } from "use-intl";

import { usePreferencesStore } from "@/features/preferences/model/preferences-provider";

import { GOOGLE_BUTTON_FILL, mountGoogleButton, watchGoogleFrame } from "../../model/brand-widgets";

/**
 * Кнопка «Продолжить с Google», нарисованная Google Identity Services, во всю ширину колонки: светлая в светлой
 * теме, тёмная в тёмной. Выше 40 px Google её не рисует, поэтому она стоит по центру рамки 44 px того же фона —
 * вровень с остальными кнопками. Пока она грузится и если скрипт Google не загрузился, на её месте — фирменная
 * ссылка входа (`fallback`).
 */
export function GoogleButton({
  clientId,
  onToken,
  fallback,
}: {
  clientId: string;
  onToken: (token: string) => void;
  fallback: ReactNode;
}) {
  const slot = useRef<HTMLDivElement>(null);
  const theme = usePreferencesStore((state) => state.resolvedThemeMode);
  const locale = useLocale();
  const [failed, setFailed] = useState(false);
  const [shown, setShown] = useState(false);
  const tokenArrived = useEffectEvent(onToken);

  useEffect(() => {
    const element = slot.current;
    if (element === null) return;
    let alive = true;
    const width = element.getBoundingClientRect().width;
    const unwatch = watchGoogleFrame(element, () => {
      if (alive) setShown(true);
    });
    mountGoogleButton(element, clientId, { theme, locale, width }, (token) => {
      if (alive) tokenArrived(token);
    }).catch(() => {
      if (alive) setFailed(true);
    });
    return () => {
      alive = false;
      unwatch();
      element.replaceChildren();
    };
  }, [clientId, theme, locale]);

  if (failed) return fallback;
  // color-scheme: light — иначе в тёмной теме браузер подкладывает под чужой светлый фрейм белый фон (полосы).
  // Рамку рисует контейнер; собственная обводка светлой кнопки Google (1 px по краю слота 40 px) срезана, иначе
  // обводка была бы двойной.
  return (
    <div className="relative isolate h-11 w-full">
      <div
        aria-hidden={!shown}
        className="flex h-11 w-full items-center justify-center overflow-hidden rounded-lg border border-zinc-300 bg-white aria-hidden:invisible dark:border-white/20 dark:bg-(--google-fill)"
        style={{ "--google-fill": GOOGLE_BUTTON_FILL, colorScheme: "light" } as CSSProperties}
      >
        <div ref={slot} className="flex w-full justify-center [clip-path:inset(1px)] dark:[clip-path:none]" />
      </div>
      {shown ? null : <div className="absolute inset-0">{fallback}</div>}
    </div>
  );
}
