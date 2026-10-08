"use client";

import type { ReactNode } from "react";

import { useTranslations } from "use-intl";

import { useDirection } from "@/components/ui/direction";
import { Sidebar } from "@/components/ui/sidebar-panel";
import { SidebarContent, SidebarFooter, SidebarHeader } from "@/components/ui/sidebar-sections";
import { APP_CONFIG } from "@/config/app-config";
import { useSidebarPreferences } from "@/features/preferences/model/preferences-provider";
import { workspacePath, workspaceSlugFromPath } from "@/features/workspace/domain/paths";
import { useWorkspaces } from "@/features/workspace/model/resources";
import { ScopeMark } from "@/features/workspace/ui/switcher/scope-mark";
import { WorkspaceSwitcher } from "@/features/workspace/ui/switcher/workspace-switcher";
import { usePathname } from "@/lib/navigation";

import { type Panel, panelHomeUrls } from "../../domain/panel";
import { adminSidebarItems } from "../admin-navigation";
import { type NavGroup, userPanelItems, workspaceSidebarItems } from "../navigation";
import { NavMain } from "./nav-main";
import { NavUser } from "./nav-user";
import { SidebarBrand } from "./sidebar-brand";
import { SidebarSearch } from "./sidebar-search";

type SidebarPartsProps = {
  panel: Panel;
  homeUrl: string;
  items: NavGroup[];
  searchGroups?: NavGroup[];
  switcher?: ReactNode;
  mark?: ReactNode;
};

function SidebarParts({ panel, homeUrl, items, searchGroups, switcher, mark }: SidebarPartsProps) {
  return (
    <>
      <SidebarHeader>
        <SidebarBrand homeUrl={homeUrl} switcher={switcher} mark={mark} />
        <SidebarSearch panel={panel} extraGroups={searchGroups} />
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={items} homeUrl={homeUrl} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser panel={panel} />
      </SidebarFooter>
    </>
  );
}

/**
 * The user panel shows Personal or one workspace, told apart by the address (`/app/w/{slug}/…`). The
 * sidebar follows: personal tools, or the workspace's shared work. Search reaches the other side too.
 */
function UserPanelParts() {
  const t = useTranslations("shell");
  const pathname = usePathname();
  const workspaces = useWorkspaces();
  const list = workspaces.status === "ready" ? workspaces.data.workspaces : [];
  const slug = workspaceSlugFromPath(pathname);
  const current = slug ? list.find((w) => w.slug === slug) : undefined;
  const workspaceList: NavGroup = {
    id: 97,
    label: t("nav.workspacesGroup"),
    items: list.map((w) => ({ id: `ws-${w.id}`, title: w.name, url: workspacePath(w.slug) })),
  };
  return (
    <SidebarParts
      panel="dashboard"
      homeUrl={slug ? workspacePath(slug) : panelHomeUrls.dashboard}
      items={slug ? workspaceSidebarItems(slug, t) : userPanelItems(t)}
      searchGroups={
        current
          ? [
              { id: 96, label: current.name, items: workspaceSidebarItems(current.slug, t).flatMap((g) => g.items) },
              workspaceList,
            ]
          : [workspaceList]
      }
      switcher={<WorkspaceSwitcher slug={slug} appName={APP_CONFIG.name} />}
      mark={<ScopeMark slug={slug} />}
    />
  );
}

export function AppSidebar({ panel, ...props }: React.ComponentProps<typeof Sidebar> & { panel: Panel }) {
  const synced = useSidebarPreferences();
  const variant = synced ? synced.variant : props.variant;
  const collapsible = synced ? synced.collapsible : props.collapsible;
  // The sidebar sits where reading starts: on the right in a right-to-left language.
  const side = useDirection() === "rtl" ? "right" : "left";

  return (
    <Sidebar {...props} side={side} variant={variant} collapsible={collapsible}>
      {panel === "dashboard" ? (
        <UserPanelParts />
      ) : (
        <SidebarParts panel={panel} homeUrl={panelHomeUrls[panel]} items={adminSidebarItems} />
      )}
    </Sidebar>
  );
}
