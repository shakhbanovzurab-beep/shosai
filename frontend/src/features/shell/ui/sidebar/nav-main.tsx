"use client";

import { useSidebar } from "@/components/ui/sidebar";
import { SidebarMenu } from "@/components/ui/sidebar-menu";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarSeparator,
} from "@/components/ui/sidebar-sections";
import { usePathname } from "@/lib/navigation";

import type { NavGroup, NavMainItem, NavMainParentItem } from "../navigation";
import { NavLinkItem } from "./nav-link-item";
import { NavCollapsibleItem, NavDropdownItem } from "./nav-parent-items";

interface NavMainProps {
  readonly items: readonly NavGroup[];
  /** The scope's home, active only on itself; every other item is also active on the pages under it. */
  readonly homeUrl: string;
}
interface NavItemProps {
  readonly item: NavMainItem;
  readonly isItemActive: (item: NavMainItem) => boolean;
  readonly isSubItemActive: (url: string) => boolean;
  readonly isSubmenuOpen: (item: NavMainParentItem) => boolean;
}

function hasSubItems(item: NavMainItem): item is NavMainParentItem {
  return Boolean(item.subItems?.length);
}

export function NavMain({ items, homeUrl }: NavMainProps) {
  const path = usePathname();

  const isItemActive = (item: NavMainItem) => {
    if (hasSubItems(item)) {
      return item.subItems.some((sub) => path.startsWith(sub.url));
    }

    return path === item.url || (item.url !== homeUrl && path.startsWith(`${item.url}/`));
  };

  const isSubItemActive = (url: string) => {
    return path === url;
  };

  const isSubmenuOpen = (item: NavMainParentItem) => {
    return item.subItems.some((sub) => path.startsWith(sub.url));
  };

  return (
    <>
      {items.map((group, index) => (
        <SidebarGroup key={group.id} className="py-1">
          {/* Unlabelled groups are set apart by a hairline, not a heading. */}
          {index > 0 && !group.label ? <SidebarSeparator className="mx-0 mb-1" /> : null}
          {group.label && (
            <SidebarGroupLabel className="group-data-[collapsible=icon]:pointer-events-none">
              {group.label}
            </SidebarGroupLabel>
          )}
          <SidebarGroupContent>
            <SidebarMenu>
              {group.items.map((item) => (
                <NavItem
                  key={item.id}
                  item={item}
                  isItemActive={isItemActive}
                  isSubItemActive={isSubItemActive}
                  isSubmenuOpen={isSubmenuOpen}
                />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      ))}
    </>
  );
}

function NavItem({ item, isItemActive, isSubItemActive, isSubmenuOpen }: NavItemProps) {
  const { state, isMobile } = useSidebar();
  const isCollapsedDesktop = state === "collapsed" && !isMobile;

  if (!hasSubItems(item)) {
    return <NavLinkItem item={item} isActive={isItemActive(item)} />;
  }

  if (isCollapsedDesktop) {
    return <NavDropdownItem item={item} isActive={isItemActive(item)} isSubItemActive={isSubItemActive} />;
  }

  return (
    <NavCollapsibleItem
      item={item}
      isActive={isItemActive(item)}
      defaultOpen={isSubmenuOpen(item)}
      isSubItemActive={isSubItemActive}
    />
  );
}
