import { isLanguageCode, type LanguageCode } from "@/lib/language";

/**
 * The language Leo answers in. Settings › Leo › Response language wins; "auto" (the default) means the
 * interface language. Leo's words are written by the model in that language, never looked up in the
 * frontend's message catalogs; only the interface around them is translated.
 */
export function answerLanguage(setting: string | undefined, interfaceLanguage: LanguageCode): LanguageCode {
  return setting && isLanguageCode(setting) ? setting : interfaceLanguage;
}
