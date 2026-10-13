"use client";

import type { ReactNode } from "react";

import { useTranslations } from "use-intl";

import { ShosaiMark } from "@/components/shosai-mark";
import { useSidebar } from "@/components/ui/sidebar";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar-menu";
import { APP_CONFIG } from "@/config/app-config";
import { Link } from "@/lib/navigation";

import { SidebarToggleButton } from "./sidebar-toggle-button";
import { SidebarToggleIcon } from "./sidebar-toggle-icon";

type SidebarBrandProps = {
  homeUrl: string;
  /** Replaces the logo link with a scope switcher, e.g. Personal and the team workspace. */
  switcher?: ReactNode;
  /** The mark the collapsed rail shows instead of the logo, e.g. the workspace's. */
  mark?: ReactNode;
};

/**
 * Logo row with the sidebar toggle at its right, like ChatGPT. In the collapsed icon rail the logo
 * itself becomes the toggle: hovering or focusing it swaps the mark for the toggle, arrow pointing open.
 */
export function SidebarBrand({ homeUrl, switcher, mark }: SidebarBrandProps) {
  const { state, isMobile, toggleSidebar } = useSidebar();
  const t = useTranslations("shell");

  if (state === "collapsed" && !isMobile) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            tooltip={t("sidebar.open")}
            aria-label={t("sidebar.open")}
            onClick={toggleSidebar}
            className="group/brand"
          >
            <span className="flex group-hover/brand:hidden group-focus-visible/brand:hidden">
              {mark ?? <ShosaiMark className="size-6!" />}
            </span>
            <SidebarToggleIcon
              direction="open"
              className="-m-0.5 hidden size-5! group-hover/brand:block group-focus-visible/brand:block"
            />
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem className="flex items-center gap-1">
        {switcher ?? (
          <SidebarMenuButton asChild className="min-w-0 flex-1">
            <Link prefetch={false} href={homeUrl}>
              <ShosaiMark className="size-6!" />
              <span className="font-semibold text-base">{APP_CONFIG.name}</span>
            </Link>
          </SidebarMenuButton>
        )}
        <SidebarToggleButton
          direction="close"
          className="shrink-0 text-sidebar-foreground/70 hover:text-sidebar-foreground"
        />
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
