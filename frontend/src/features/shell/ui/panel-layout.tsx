import type { ReactNode } from "react";

import { cookies } from "next/headers";

import { cn } from "cn";
import { getLocale } from "next-intl/server";

import { SidebarProvider } from "@/components/ui/sidebar";
import { SidebarInset } from "@/components/ui/sidebar-panel";
import { LeoWidget } from "@/features/leo";
import { LayoutControls, readSidebarPreferences } from "@/features/preferences";
import { SettingsDialog } from "@/features/settings";
import { LocaleGuard } from "@/i18n/locale-guard";

import type { Panel } from "../domain/panel";
import { HeaderSidebarTrigger } from "./header/header-sidebar-trigger";
import { HeaderToday } from "./header/header-today";
import { AppSidebar } from "./sidebar/app-sidebar";
import { UserPanelLeo } from "./user-panel-leo";

export async function PanelLayout({ panel, children }: Readonly<{ panel: Panel; children: ReactNode }>) {
  const [cookieStore, locale] = await Promise.all([cookies(), getLocale()]);
  const defaultOpen = cookieStore.get("sidebar_state")?.value !== "false";
  const { variant, collapsible } = readSidebarPreferences(cookieStore);

  return (
    <SidebarProvider
      defaultOpen={defaultOpen}
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 68)",
        } as React.CSSProperties
      }
    >
      <AppSidebar panel={panel} variant={variant} collapsible={collapsible} />
      <SidebarInset
        className={cn(
          "[html[data-content-layout=centered]_&>*]:mx-auto",
          "[html[data-content-layout=centered]_&>*]:w-full",
          "[html[data-content-layout=centered]_&>*]:max-w-screen-2xl",
          "peer-data-[variant=inset]:border",
          // i18n-ignore: SidebarInset (components/ui) sets physical margins for a left sidebar; this mirrors them.
          "rtl:md:peer-data-[variant=inset]:mr-0 rtl:md:peer-data-[variant=inset]:ml-2 rtl:md:peer-data-[variant=inset]:peer-data-[state=collapsed]:mr-2",
          "[--dashboard-header-height:--spacing(12)]",
          "min-w-0 overflow-x-clip",
        )}
      >
        <header
          className={cn(
            "flex h-12 shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12",
            // Handle sticky navbar style with conditional classes so blur, background, z-index, and rounded corners remain consistent across all SidebarVariant layouts.
            "[html[data-navbar-style=sticky]_&]:sticky [html[data-navbar-style=sticky]_&]:top-0 [html[data-navbar-style=sticky]_&]:z-50 [html[data-navbar-style=sticky]_&]:overflow-hidden [html[data-navbar-style=sticky]_&]:rounded-t-[inherit] [html[data-navbar-style=sticky]_&]:bg-background/50 [html[data-navbar-style=sticky]_&]:backdrop-blur-md",
          )}
        >
          <div className="relative flex w-full items-center justify-between px-4 lg:px-6">
            <div className="flex items-center gap-1 lg:gap-2">
              <HeaderSidebarTrigger collapsible={collapsible} />
            </div>
            <div className="absolute left-1/2 hidden -translate-x-1/2 sm:flex">
              <HeaderToday />
            </div>
            <div className="flex items-center gap-2">
              <LayoutControls />
            </div>
          </div>
        </header>
        {/* Pages can set data-content-padding="false" to render full-bleed app layouts. */}
        <div className="min-h-0 min-w-0 flex-1 overflow-x-hidden p-4 has-data-[content-padding=false]:p-0 md:p-6 md:has-data-[content-padding=false]:p-0">
          <LocaleGuard locale={locale} />
          {children}
        </div>
      </SidebarInset>
      {panel === "dashboard" ? <UserPanelLeo /> : <LeoWidget />}
      <SettingsDialog />
    </SidebarProvider>
  );
}
