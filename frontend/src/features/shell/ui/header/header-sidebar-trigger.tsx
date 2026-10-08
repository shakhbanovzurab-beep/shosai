"use client";

import { useSidebar } from "@/components/ui/sidebar";
import type { SidebarPreferences } from "@/features/preferences/domain/sidebar-preferences";
import { useSidebarPreferences } from "@/features/preferences/model/preferences-provider";

import { SidebarToggleButton } from "../sidebar/sidebar-toggle-button";

/**
 * The header's sidebar toggle, shown only when the sidebar can't offer its own: on mobile, or when
 * it is fully hidden (offcanvas). In every other state the toggle lives in the sidebar itself.
 */
export function HeaderSidebarTrigger({ collapsible }: { collapsible: SidebarPreferences["collapsible"] }) {
  const { state, isMobile } = useSidebar();
  const mode = useSidebarPreferences()?.collapsible ?? collapsible;

  if (!isMobile && !(state === "collapsed" && mode === "offcanvas")) return null;
  return <SidebarToggleButton direction="open" className="-ms-1" />;
}
