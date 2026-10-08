import { DEFAULT_LANGUAGE, isLanguageCode, type LanguageCode } from "@/lib/language";

/** Язык страницы (`<html lang>`, ставится до первой отрисовки и при каждой смене языка). */
export function interfaceLanguage(): LanguageCode {
  if (typeof document === "undefined") return DEFAULT_LANGUAGE;
  const lang = document.documentElement.lang;
  return isLanguageCode(lang) ? lang : DEFAULT_LANGUAGE;
}
