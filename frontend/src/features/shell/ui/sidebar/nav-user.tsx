"use client";

import { CircleArrowUp, Download, EllipsisVertical, Languages, LifeBuoy, LogOut, Settings } from "lucide-react";
import { useTranslations } from "use-intl";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu-items";
import { DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger } from "@/components/ui/dropdown-menu-sub";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar-menu";
import { useOpenSettings } from "@/features/settings/model/dialog-store";
import { useAccountProfile } from "@/features/settings/model/settings-hooks";
import { useSwitchLanguage } from "@/hooks/use-switch-language";
import { LANGUAGES } from "@/lib/language";
import { Link } from "@/lib/navigation";
import { getInitials } from "@/lib/utils";

import type { Panel } from "../../domain/panel";
import { downloadAppItem } from "../navigation";

export function NavUser({ panel }: { readonly panel: Panel }) {
  const t = useTranslations("shell");
  // Once settings load, the photo and name the user set there; until then, the demo account's.
  const { name, email, avatar } = useAccountProfile();

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="h-8 w-8 rounded-lg">
                <AvatarImage src={avatar || undefined} alt={name} />
                <AvatarFallback className="rounded-lg">{getInitials(name)}</AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-start text-sm leading-tight">
                <span className="truncate font-medium">{name}</span>
                <span className="truncate text-muted-foreground text-xs">{email}</span>
              </div>
              <EllipsisVertical className="ms-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side="top"
            align="start"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-start text-sm">
                <Avatar className="h-8 w-8 rounded-lg">
                  <AvatarImage src={avatar || undefined} alt={name} />
                  <AvatarFallback className="rounded-lg">{getInitials(name)}</AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-start text-sm leading-tight">
                  <span className="truncate font-medium">{name}</span>
                  <span className="truncate text-muted-foreground text-xs">{email}</span>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {panel === "dashboard" ? <UserPanelItems /> : null}
            <DropdownMenuItem>
              <LogOut className="rtl:-scale-x-100" />
              {t("userMenu.logOut")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

/** Account items of the user panel; the admin panel's menu only lets the admin sign out. */
function UserPanelItems() {
  const t = useTranslations("shell");
  const openSettings = useOpenSettings();
  const { language, switchLanguage } = useSwitchLanguage();

  return (
    <>
      <DropdownMenuGroup>
        <DropdownMenuItem onSelect={() => openSettings()}>
          <Settings />
          {t("userMenu.settings")}
        </DropdownMenuItem>
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <Languages />
            {t("userMenu.language")}
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="max-h-80 w-52 overflow-y-auto">
            <DropdownMenuRadioGroup value={language} onValueChange={switchLanguage}>
              {LANGUAGES.map((option) => (
                <DropdownMenuRadioItem key={option.code} value={option.code}>
                  {/* Tagged with its own language so screen readers and fonts treat the name correctly. */}
                  <span lang={option.code} dir="auto">
                    {option.label}
                  </span>
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuItem asChild>
          <Link href="/app/upgrade">
            <CircleArrowUp />
            {t("userMenu.upgrade")}
          </Link>
        </DropdownMenuItem>
      </DropdownMenuGroup>
      <DropdownMenuSeparator />
      <DropdownMenuGroup>
        <DropdownMenuItem asChild>
          <Link href="/app/support">
            <LifeBuoy />
            {t("userMenu.support")}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href={downloadAppItem(t).url}>
            <Download />
            {t("nav.downloadApp")}
          </Link>
        </DropdownMenuItem>
      </DropdownMenuGroup>
      <DropdownMenuSeparator />
    </>
  );
}
