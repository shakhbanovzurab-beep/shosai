/**
 * Поддерживаемые языки платформы — единый реестр фронтенда.
 *
 * Порядок записей — порядок пунктов в переключателе языка. Модуль без
 * импортов: его читают и приложение, и генератор шрифтов `scripts/fonts/`.
 */

export interface Locale {
  /** Код в URL, каталогах строк, `wh.lang` и профиле пользователя. */
  readonly code: string;
  /** BCP-47 для `<html lang>` и hreflang; у китайского — традиционное письмо. */
  readonly hreflang: string;
  /** Название языка на нём самом — подпись в переключателе. */
  readonly endonym: string;
  /** `og:locale` для соцсетей. */
  readonly ogLocale: string;
  /** Направление письма справа налево. */
  readonly rtl: boolean;
}

export const LOCALES = [
  { code: "en", hreflang: "en", endonym: "English", ogLocale: "en_US", rtl: false },
  { code: "zh", hreflang: "zh-Hant", endonym: "中文（繁體）", ogLocale: "zh_TW", rtl: false },
  { code: "es", hreflang: "es", endonym: "Español", ogLocale: "es_ES", rtl: false },
  { code: "ru", hreflang: "ru", endonym: "Русский", ogLocale: "ru_RU", rtl: false },
  { code: "hi", hreflang: "hi", endonym: "हिन्दी", ogLocale: "hi_IN", rtl: false },
  { code: "ar", hreflang: "ar", endonym: "العربية", ogLocale: "ar_AR", rtl: true },
  { code: "pt", hreflang: "pt", endonym: "Português", ogLocale: "pt_BR", rtl: false },
  { code: "fr", hreflang: "fr", endonym: "Français", ogLocale: "fr_FR", rtl: false },
  { code: "it", hreflang: "it", endonym: "Italiano", ogLocale: "it_IT", rtl: false },
  { code: "de", hreflang: "de", endonym: "Deutsch", ogLocale: "de_DE", rtl: false },
  { code: "ja", hreflang: "ja", endonym: "日本語", ogLocale: "ja_JP", rtl: false },
  { code: "ko", hreflang: "ko", endonym: "한국어", ogLocale: "ko_KR", rtl: false },
  { code: "id", hreflang: "id", endonym: "Bahasa Indonesia", ogLocale: "id_ID", rtl: false },
  { code: "tr", hreflang: "tr", endonym: "Türkçe", ogLocale: "tr_TR", rtl: false },
  { code: "vi", hreflang: "vi", endonym: "Tiếng Việt", ogLocale: "vi_VN", rtl: false },
  { code: "th", hreflang: "th", endonym: "ไทย", ogLocale: "th_TH", rtl: false },
] as const satisfies readonly Locale[];

export type LanguageCode = (typeof LOCALES)[number]["code"];
