import { type ReactNode, useEffect } from "react";

import { IntlProvider } from "use-intl";

import { DirectionProvider } from "@/components/ui/direction";
import { type LanguageCode, languageDirection } from "@/lib/language";

import { loadedCatalogue } from "./catalogues";
import { formats } from "./formats";
import { useTimeZone } from "./time-zone";

/**
 * Язык страницы для всех компонентов (сообщения, форматы, часовой пояс кабинета — `time-zone.ts`) и направление текста для примитивов
 * Radix. Корневой маршрут загружает каталог до отрисовки, поэтому смена языка — выбор пользователя или переход
 * между пользовательской и админ-панелью — никогда не показывает смесь двух языков.
 */
export function I18nProvider({ locale, children }: Readonly<{ locale: LanguageCode; children: ReactNode }>) {
  const dir = languageDirection(locale);
  const timeZone = useTimeZone();
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = dir;
  }, [locale, dir]);
  return (
    <IntlProvider locale={locale} messages={loadedCatalogue(locale)} formats={formats} timeZone={timeZone}>
      <DirectionProvider dir={dir}>{children}</DirectionProvider>
    </IntlProvider>
  );
}
