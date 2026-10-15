import { type ReactNode, useEffect, useEffectEvent, useRef, useState } from "react";

import { useLocale } from "use-intl";

import { usePreferencesStore } from "@/features/preferences/model/preferences-provider";

import { mountGoogleButton } from "../../model/brand-widgets";

/**
 * Кнопка «Продолжить с Google», нарисованная Google Identity Services, во всю ширину колонки. Если скрипт Google
 * не загрузился, вместо неё — фирменная ссылка входа (`fallback`).
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
  const tokenArrived = useEffectEvent(onToken);

  useEffect(() => {
    const element = slot.current;
    if (element === null) return;
    let alive = true;
    const width = element.getBoundingClientRect().width;
    mountGoogleButton(element, clientId, { theme, locale, width }, (token) => {
      if (alive) tokenArrived(token);
    }).catch(() => {
      if (alive) setFailed(true);
    });
    return () => {
      alive = false;
      element.replaceChildren();
    };
  }, [clientId, theme, locale]);

  if (failed) return fallback;
  return <div ref={slot} className="flex h-11 w-full justify-center overflow-hidden" />;
}
