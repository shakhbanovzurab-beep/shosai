"use client";

import { ChevronRight } from "lucide-react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useDirection } from "@/components/ui/direction";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar-menu";
import { SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem } from "@/components/ui/sidebar-menu-sub";
import { Link } from "@/lib/navigation";

import type { NavMainParentItem } from "../navigation";
import { NavIcon, navButtonClass } from "./nav-icon";
import { NavItemBadge } from "./nav-link-item";

interface NavDropdownItemProps {
  readonly item: NavMainParentItem;
  readonly isActive: boolean;
  readonly isSubItemActive: (url: string) => boolean;
}

interface NavCollapsibleItemProps extends NavDropdownItemProps {
  readonly defaultOpen: boolean;
}

export function NavDropdownItem({ item, isActive, isSubItemActive }: NavDropdownItemProps) {
  // The collapsed sidebar's submenu opens towards the page: right of it, or left of it right to left.
  const submenuSide = useDirection() === "rtl" ? "left" : "right";
  return (
    <SidebarMenuItem>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <SidebarMenuButton
            tooltip={item.title}
            isActive={isActive}
            disabled={item.disabled}
            className={navButtonClass}
          >
            <NavIcon icon={item.icon} title={item.title} />
            <span>{item.title}</span>
          </SidebarMenuButton>
        </DropdownMenuTrigger>

        <DropdownMenuContent side={submenuSide} align="start" sideOffset={12} className="w-48">
          <DropdownMenuGroup>
            {item.subItems.map((subItem) => {
              const SubIcon = subItem.icon;

              return (
                <DropdownMenuItem key={subItem.id} asChild disabled={subItem.disabled}>
                  <Link
                    prefetch={false}
                    href={subItem.url}
                    target={subItem.newTab ? "_blank" : undefined}
                    rel={subItem.newTab ? "noreferrer" : undefined}
                    aria-current={isSubItemActive(subItem.url) ? "page" : undefined}
                    className="flex items-center gap-2"
                  >
                    {SubIcon && <SubIcon />}
                    <span>{subItem.title}</span>
                  </Link>
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  );
}

export function NavCollapsibleItem({ item, isActive, defaultOpen, isSubItemActive }: NavCollapsibleItemProps) {
  return (
    <Collapsible asChild defaultOpen={defaultOpen} className="group/collapsible">
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton
            tooltip={item.title}
            isActive={isActive}
            disabled={item.disabled}
            className={navButtonClass}
          >
            <NavIcon icon={item.icon} title={item.title} />
            <span>{item.title}</span>
            {/* Points to the end of the line when closed and down when open, in either direction. */}
            <ChevronRight className="ms-auto transition-transform duration-200 ltr:group-data-[state=open]/collapsible:rotate-90 rtl:-scale-x-100 rtl:group-data-[state=open]/collapsible:-rotate-90" />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <NavItemBadge badge={item.badge} />

        <CollapsibleContent>
          <SidebarMenuSub>
            {item.subItems.map((subItem) => {
              const SubIcon = subItem.icon;

              return (
                <SidebarMenuSubItem key={subItem.id}>
                  <SidebarMenuSubButton
                    asChild
                    aria-disabled={subItem.disabled}
                    isActive={isSubItemActive(subItem.url)}
                  >
                    <Link
                      prefetch={false}
                      href={subItem.url}
                      target={subItem.newTab ? "_blank" : undefined}
                      rel={subItem.newTab ? "noreferrer" : undefined}
                    >
                      {SubIcon && <SubIcon />}
                      <span>{subItem.title}</span>
                    </Link>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>
              );
            })}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  );
}
