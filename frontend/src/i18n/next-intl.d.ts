import type { LanguageCode } from "@/lib/language";

import type { formats } from "./formats";
import type { Messages } from "./namespaces";

// Typed keys, ICU arguments, locales and format names for useTranslations, getTranslations and useFormatter.
declare module "next-intl" {
  interface AppConfig {
    Locale: LanguageCode;
    Messages: Messages;
    Formats: typeof formats;
  }
}
