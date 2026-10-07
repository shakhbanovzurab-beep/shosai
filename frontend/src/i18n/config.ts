import type { LanguageCode } from "@/lib/language";

/** Request header the proxy sets on admin pages, which are written in Russian only. */
export const PANEL_HEADER = "x-studio-panel";
export const ADMIN_PANEL = "admin";
export const ADMIN_LANGUAGE: LanguageCode = "ru";

/**
 * The time zone `next-intl` formats in, on the server and in the browser alike, so server-rendered dates
 * hydrate unchanged. Demo data and the domain formatters are UTC; a component that shows the viewer's
 * wall-clock time (the header clock) formats it in the browser itself. See docs/i18n.md.
 */
export const TIME_ZONE = "UTC";
