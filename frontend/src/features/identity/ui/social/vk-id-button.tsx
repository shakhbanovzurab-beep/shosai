import { type ReactNode, useEffect, useEffectEvent, useRef, useState } from "react";

import { useLocale } from "use-intl";

import { usePreferencesStore } from "@/features/preferences/model/preferences-provider";

import { mountVkOneTap, type VkCode } from "../../model/vk-widget";

interface VkIdButtonProps {
  appId: number;
  next: string;
  onCode: (answer: VkCode) => void;
  fallback: ReactNode;
}

/**
 * Кнопка VK ID OneTap, нарисованная SDK VK: «Продолжить как …» для человека, вошедшего в VK, иначе «Войти с VK ID».
 * Пока виджет грузится, на её месте — фирменная ссылка входа (`fallback`); она же остаётся, если не загрузился сам
 * SDK или сервер не открыл поток. Сбой фрейма VK (например, через VPN) ссылкой не заменяется: SDK ставит свою
 * кнопку, которая открывает окно VK ID.
 */
export function VkIdButton({ appId, next, onCode, fallback }: VkIdButtonProps) {
  const slot = useRef<HTMLDivElement>(null);
  const theme = usePreferencesStore((state) => state.resolvedThemeMode);
  const language = useLocale();
  const [shown, setShown] = useState(false);
  const [failed, setFailed] = useState(false);
  const codeArrived = useEffectEvent(onCode);

  useEffect(() => {
    const element = slot.current;
    if (element === null) return;
    let alive = true;
    let close: (() => void) | null = null;
    const events = {
      onShown: () => {
        if (alive) setShown(true);
      },
      onCode: (answer: VkCode) => {
        if (alive) codeArrived(answer);
      },
      onFailed: () => {
        if (alive) setFailed(true);
      },
    };
    mountVkOneTap(element, appId, { theme, language, next }, events)
      .then((closeWidget) => {
        if (alive) close = closeWidget;
        else closeWidget();
      })
      .catch(events.onFailed);
    return () => {
      alive = false;
      close?.();
      element.replaceChildren();
    };
  }, [appId, theme, language, next]);

  if (failed) return fallback;
  // isolate: фрейм VK ставит свой z-index; без своего слоя наложения он перекрывал бы меню страницы. Пока виджет под
  // ссылкой, inert убирает его кнопку и фрейм из фокуса и дерева доступности.
  return (
    <div className="relative isolate h-11 w-full">
      <div ref={slot} inert={!shown} className="h-11 w-full overflow-hidden rounded-lg" />
      {shown ? null : <div className="absolute inset-0">{fallback}</div>}
    </div>
  );
}
