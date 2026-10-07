"use client";

import Link from "next/link";

import { cn } from "cn";
import { useTranslations } from "next-intl";

import { SidebarMenuBadge, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";

import type { NavBadge, NavMainLinkItem } from "../navigation";
import { NavIcon, navButtonClass } from "./nav-icon";

export function NavLinkItem({ item, isActive }: { readonly item: NavMainLinkItem; readonly isActive: boolean }) {
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        aria-disabled={item.disabled}
        tooltip={item.title}
        isActive={isActive}
        className={navButtonClass}
      >
        <Link
          prefetch={false}
          href={item.url}
          target={item.newTab ? "_blank" : undefined}
          rel={item.newTab ? "noreferrer" : undefined}
          aria-current={isActive ? "page" : undefined}
        >
          <NavIcon icon={item.icon} title={item.title} />
          <span>{item.title}</span>
        </Link>
      </SidebarMenuButton>
      <NavItemBadge badge={item.badge} />
    </SidebarMenuItem>
  );
}

export function NavItemBadge({ badge }: { badge?: NavBadge }) {
  const t = useTranslations("shell");
  if (!badge) {
    return null;
  }

  return (
    <SidebarMenuBadge
      className={cn(
        "rounded-sm border",
        badge === "new" &&
          "border-green-600 text-green-600 peer-hover/menu-button:text-green-600 peer-data-active/menu-button:text-green-600",
        badge === "soon" && "border-muted-foreground text-muted-foreground",
      )}
    >
      {t(`badge.${badge}`)}
    </SidebarMenuBadge>
  );
}
