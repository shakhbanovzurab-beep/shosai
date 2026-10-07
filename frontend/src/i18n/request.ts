import { cookies, headers } from "next/headers";

import { getRequestConfig } from "next-intl/server";

import { LANGUAGE_COOKIE } from "@/lib/language";

import { PANEL_HEADER, TIME_ZONE } from "./config";
import { formats } from "./formats";
import { loadMessages } from "./messages";
import { resolveLocale } from "./resolve-locale";

/** The language, messages and formats of a request: `next-intl` reads this for every Server Component. */
export default getRequestConfig(async () => {
  const [headerStore, cookieStore] = await Promise.all([headers(), cookies()]);
  const locale = resolveLocale(headerStore.get(PANEL_HEADER), cookieStore.get(LANGUAGE_COOKIE)?.value);
  return { locale, messages: await loadMessages(locale), formats, timeZone: TIME_ZONE };
});
