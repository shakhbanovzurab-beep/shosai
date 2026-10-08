import type { SidebarCollapsible, SidebarVariant } from "./layout";
import { preferenceFromCookie } from "./registry";

/** The sidebar's layout preferences, read when the panel first renders so the sidebar shows without a flash. */
export type SidebarPreferences = { variant: SidebarVariant; collapsible: SidebarCollapsible };

/** Reads one cookie by name; null when it is not set. */
type CookieReader = (name: string) => string | null;

/** Reads the sidebar preferences from the cookies, falling back to the defaults. */
export function readSidebarPreferences(readCookie: CookieReader): SidebarPreferences {
  return {
    variant: preferenceFromCookie("sidebar_variant", readCookie("sidebar_variant")),
    collapsible: preferenceFromCookie("sidebar_collapsible", readCookie("sidebar_collapsible")),
  };
}
