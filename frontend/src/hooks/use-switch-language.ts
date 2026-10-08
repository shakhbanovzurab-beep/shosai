import { useState } from "react";

import { useRevalidator } from "react-router";

import { setClientCookie } from "@/lib/cookie.client";
import { isLanguageCode, LANGUAGE_COOKIE, type LanguageCode } from "@/lib/language";

import { useUiLanguage } from "./use-ui-language";

const YEAR_DAYS = 365;

/**
 * Язык интерфейса и способ его сменить. Выбор хранится в cookie; перепроверка маршрутов загружает новый каталог
 * и перерисовывает страницу на месте, без перезагрузки. Пока это идёт, `language` уже показывает новый выбор,
 * так что галочка в списке переключается сразу.
 */
export function useSwitchLanguage() {
  const revalidator = useRevalidator();
  const current = useUiLanguage();
  const [chosen, setChosen] = useState<LanguageCode | null>(null);

  const switchLanguage = (code: string) => {
    if (!isLanguageCode(code)) return;
    setClientCookie(LANGUAGE_COOKIE, code, YEAR_DAYS);
    setChosen(code);
    void revalidator.revalidate().finally(() => setChosen(null));
  };

  return { language: chosen ?? current, switchLanguage };
}
