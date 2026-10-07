/** Interface languages the user can pick. The server reads the cookie and renders the page in that language. */
export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" },
  { code: "ru", label: "Русский" },
  { code: "nl", label: "Nederlands" },
  { code: "it", label: "Italiano" },
  { code: "es", label: "Español" },
  { code: "pt-BR", label: "Português (Brasil)" },
  { code: "ar", label: "العربية" },
  { code: "tr", label: "Türkçe" },
  { code: "ko", label: "한국어" },
  { code: "hi", label: "हिन्दी" },
  { code: "vi", label: "Tiếng Việt" },
  { code: "zh-Hant", label: "繁體中文" },
  { code: "ja", label: "日本語" },
  { code: "id", label: "Bahasa Indonesia" },
] as const;

export type LanguageCode = (typeof LANGUAGES)[number]["code"];

/** Every code, in menu order; a non-empty tuple, so it can feed `z.enum`. */
export const LANGUAGE_CODES = LANGUAGES.map((l) => l.code) as [LanguageCode, ...LanguageCode[]];

export const LANGUAGE_COOKIE = "ui_language";
export const DEFAULT_LANGUAGE: LanguageCode = "en";

export const isLanguageCode = (value: string): value is LanguageCode => LANGUAGES.some((l) => l.code === value);

export type TextDirection = "ltr" | "rtl";

const RIGHT_TO_LEFT: ReadonlySet<LanguageCode> = new Set(["ar"]);

/** The direction a language is written in: `<html dir>` and Radix primitives follow it. */
export const languageDirection = (code: LanguageCode): TextDirection => (RIGHT_TO_LEFT.has(code) ? "rtl" : "ltr");
