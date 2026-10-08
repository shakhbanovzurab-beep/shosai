"use client";

import * as React from "react";

import { PenLine } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { useDirection } from "@/components/ui/direction";
import { Separator } from "@/components/ui/separator";
import { useSidebar } from "@/components/ui/sidebar";
import { SidebarMenu, SidebarMenuBadge, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar-menu";
import { Sidebar } from "@/components/ui/sidebar-panel";
import {
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
} from "@/components/ui/sidebar-sections";

import { accounts } from "../data/accounts";
import { MailAccountSwitcher } from "./mail-account-switcher";
import { type MailNavItem, mailNavigation } from "./mail-navigation";

export function MailSidebar() {
  const t = useTranslations("mail");
  const { state } = useSidebar();
  const isCollapsed = state === "collapsed";
  const [selectedAccount, setSelectedAccount] = React.useState(accounts[0]);
  // The sidebar sits where reading starts: on the right in a right-to-left language.
  const side = useDirection() === "rtl" ? "right" : "left";

  return (
    <Sidebar
      side={side}
      collapsible="icon"
      className="absolute inset-y-0 h-full **:data-[sidebar=sidebar]:bg-background"
    >
      <SidebarHeader className="gap-3 py-3 pb-1">
        <div className="flex items-center justify-between">
          <MailAccountSwitcher selectedAccount={selectedAccount} onSelectAccount={setSelectedAccount} />
        </div>

        <Separator />

        <div className="flex flex-col gap-1.5 group-data-[state=collapsed]:hidden">
          <div dir="auto" className="font-medium text-sm leading-none">
            {selectedAccount.name}
          </div>
          <div className="truncate text-muted-foreground text-sm leading-none">{selectedAccount.email}</div>
        </div>

        <Button size={isCollapsed ? "icon-sm" : "sm"} variant="outline" className="group-data-[state=expanded]:w-full">
          <PenLine data-icon="inline-start" />
          <span className="group-data-[state=collapsed]:hidden">{t("sidebar.newEmail")}</span>
        </Button>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu className="gap-1">
            {mailNavigation.navMain.map((nav) => (
              <NavItem key={nav.id} nav={nav} />
            ))}
          </SidebarMenu>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel className="font-normal">{t("sidebar.folders")}</SidebarGroupLabel>
          <SidebarMenu className="gap-1">
            {mailNavigation.folders.map((nav) => (
              <NavItem key={nav.id} nav={nav} />
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu className="gap-1">
          {mailNavigation.navFooter.map((nav) => (
            <NavItem key={nav.id} nav={nav} />
          ))}
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}

function NavItem({ nav }: { nav: MailNavItem }) {
  const t = useTranslations("mail.nav");
  const format = useFormatter();
  const title = t(nav.id);

  return (
    <SidebarMenuItem>
      <SidebarMenuButton className="[&_svg]:size-3.5" size="sm" isActive={nav.isActive} tooltip={title}>
        <nav.icon />
        <span className="font-medium">{title}</span>
      </SidebarMenuButton>
      {nav.count === undefined ? null : (
        <SidebarMenuBadge className="font-medium">{format.number(nav.count)}</SidebarMenuBadge>
      )}
    </SidebarMenuItem>
  );
}
