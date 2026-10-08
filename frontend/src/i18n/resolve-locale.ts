import { DEFAULT_LANGUAGE, isLanguageCode, type LanguageCode } from "@/lib/language";

import { ADMIN_LANGUAGE, isAdminPath } from "./config";

/**
 * Язык страницы: админ-панель всегда на русском; остальное — на языке, выбранном пользователем (cookie),
 * или на английском.
 */
export function resolveLocale(pathname: string, cookie: string | null | undefined): LanguageCode {
  if (isAdminPath(pathname)) return ADMIN_LANGUAGE;
  return cookie && isLanguageCode(cookie) ? cookie : DEFAULT_LANGUAGE;
}
