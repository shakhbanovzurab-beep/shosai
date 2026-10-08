import type { LoaderFunctionArgs } from "react-router";

import { loadCatalogue } from "@/i18n/catalogues";
import { resolveLocale } from "@/i18n/resolve-locale";
import { readClientCookie } from "@/lib/cookie.client";
import { LANGUAGE_COOKIE, type LanguageCode } from "@/lib/language";

export interface RootData {
  locale: LanguageCode;
}

/**
 * До отрисовки любой страницы: её язык (админка — русская, остальное — по выбору пользователя) и каталог.
 * Выполняется при каждой навигации, поэтому переход между панелями или смена языка отрисовывает следующую
 * страницу целиком на её языке; загруженный каталог повторно не скачивается.
 */
export async function rootLoader({ request }: LoaderFunctionArgs): Promise<RootData> {
  const locale = resolveLocale(new URL(request.url).pathname, readClientCookie(LANGUAGE_COOKIE));
  await loadCatalogue(locale);
  return { locale };
}

export const revalidateRoot = () => true;
