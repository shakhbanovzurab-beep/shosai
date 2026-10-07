import { DEFAULT_LANGUAGE, isLanguageCode, type LanguageCode } from "@/lib/language";

import { ADMIN_LANGUAGE, ADMIN_PANEL } from "./config";

/**
 * The language a request is rendered in: the admin panel is always Russian; everything else follows the
 * language the user picked (the cookie), or English.
 */
export function resolveLocale(panel: string | null | undefined, cookie: string | null | undefined): LanguageCode {
  if (panel === ADMIN_PANEL) return ADMIN_LANGUAGE;
  return cookie && isLanguageCode(cookie) ? cookie : DEFAULT_LANGUAGE;
}
