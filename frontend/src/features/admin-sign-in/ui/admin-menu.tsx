"use client";

import { LogOut, ShieldCheck } from "lucide-react";

import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar-menu";

import { useAdminSignOut } from "../model/admin-session";

/** Низ боковой панели админки: администратор — не аккаунт человека, поэтому вместо профиля только выход. */
export function AdminMenu() {
  const signOut = useAdminSignOut();
  return (
    <SidebarMenu>
      <SidebarMenuItem className="flex items-center gap-2 px-2 py-1.5 text-sm">
        <ShieldCheck aria-hidden="true" className="size-4 text-muted-foreground" />
        <span className="truncate font-medium">Администратор</span>
      </SidebarMenuItem>
      <SidebarMenuItem>
        <SidebarMenuButton onClick={signOut}>
          <LogOut aria-hidden="true" />
          Выйти
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
