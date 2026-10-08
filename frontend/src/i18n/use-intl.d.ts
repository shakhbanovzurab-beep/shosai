import type { LanguageCode } from "@/lib/language";

import type { formats } from "./formats";
import type { Messages } from "./messages-type";

// Типизированные ключи, аргументы ICU, языки и имена форматов для useTranslations, createTranslator и useFormatter.
declare module "use-intl" {
  interface AppConfig {
    Locale: LanguageCode;
    Messages: Messages;
    Formats: typeof formats;
  }
}
