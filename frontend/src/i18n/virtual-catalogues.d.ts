// Модуль плагина tooling/i18n-catalogues.ts: адрес файла сообщений каждого языка.
declare module "virtual:i18n-catalogues" {
  import type { LanguageCode } from "@/lib/language";

  export const catalogueUrls: Readonly<Record<LanguageCode, string>>;
}

// Модуль плагина tooling/i18n-catalogues.ts: тексты страницы сбоя на каждом языке.
declare module "virtual:i18n-failure-texts" {
  import type { LanguageCode } from "@/lib/language";

  export const failureTexts: Readonly<
    Record<LanguageCode, { readonly title: string; readonly description: string; readonly reload: string }>
  >;
}
