import type { SidebarCollapsible, SidebarVariant } from "./layout";
import { preferenceFromCookie } from "./registry";

/** The sidebar's layout preferences, which the server needs to render the sidebar without a flash. */
export type SidebarPreferences = { variant: SidebarVariant; collapsible: SidebarCollapsible };

/** The request's cookies, as `cookies()` from next/headers returns them. */
type CookieReader = { get: (name: string) => { value: string } | undefined };

/** Reads the sidebar preferences from the request's cookies, falling back to the defaults. */
export function readSidebarPreferences(cookies: CookieReader): SidebarPreferences {
  return {
    variant: preferenceFromCookie("sidebar_variant", cookies.get("sidebar_variant")?.value),
    collapsible: preferenceFromCookie("sidebar_collapsible", cookies.get("sidebar_collapsible")?.value),
  };
}
