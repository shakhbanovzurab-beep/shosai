"use client";

import * as React from "react";

import { Search } from "lucide-react";
import { useTranslations } from "use-intl";

import {
  Command,
  CommandDialog,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Kbd } from "@/components/ui/kbd";
import { useSidebar } from "@/components/ui/sidebar";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar-menu";
import { askLeo } from "@/features/leo/model/leo-questions";
import { useRouter } from "@/lib/navigation";

import type { Panel } from "../../domain/panel";
import { adminSidebarItems } from "../admin-navigation";
import { downloadAppItem, type NavGroup, type NavMainItem, type ShellT, userPanelItems } from "../navigation";
import { AskLeoItem } from "./ask-leo-item";

type SearchItem = {
  id: string;
  group: string;
  label: string;
  url: string;
  icon?: NavMainItem["icon"];
  disabled?: boolean;
  newTab?: boolean;
};

function getSearchItems(groups: NavGroup[], defaultGroup: string): SearchItem[] {
  const groupLabels = new Set(groups.flatMap((group) => (group.label ? [group.label] : [])));
  const getSubItemGroup = (groupLabel: string | undefined, itemTitle: string) =>
    groupLabels.has(itemTitle) ? (groupLabel ?? defaultGroup) : itemTitle;

  return groups.flatMap((group) =>
    group.items.flatMap((item) => {
      if (item.subItems) {
        return item.subItems.map((sub) => ({
          id: sub.id,
          group: getSubItemGroup(group.label, item.title),
          label: sub.title,
          url: sub.url,
          icon: item.icon,
          disabled: sub.disabled,
          newTab: sub.newTab,
        }));
      }
      return [
        {
          id: item.id,
          group: group.label ?? defaultGroup,
          label: item.title,
          url: item.url,
          icon: item.icon,
          disabled: item.disabled,
          newTab: item.newTab,
        },
      ];
    }),
  );
}

/** Every page of a panel, grouped as in its sidebar; pages outside any group fall under "Pages". */
function panelSearchItems(panel: Panel, t: ShellT): SearchItem[] {
  const pages = t("search.pagesGroup");
  if (panel === "admin") return getSearchItems(adminSidebarItems, pages);
  return getSearchItems(
    [...userPanelItems(t), { id: 99, label: t("nav.appGroup"), items: [downloadAppItem(t)] }],
    pages,
  );
}

function groupBy(items: SearchItem[]) {
  const groups = [...new Set(items.map((item) => item.group))];
  return groups.map((group) => ({
    group,
    items: items.filter((item) => item.group === group),
  }));
}

/**
 * Page search. `extraGroups` adds pages that depend on the account, e.g. the open workspace's pages
 * or the list of workspaces, so search also moves between Personal and workspaces. Набранный текст можно
 * отдать вопросом Leo — последней строкой списка.
 */
export function SidebarSearch({ panel, extraGroups = [] }: { panel: Panel; extraGroups?: NavGroup[] }) {
  const t = useTranslations("shell");
  const base = panelSearchItems(panel, t);
  const searchItems = extraGroups.length ? [...getSearchItems(extraGroups, t("search.pagesGroup")), ...base] : base;
  const recommendations = searchItems.filter((item) => !item.disabled);
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const router = useRouter();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.key === "k" || e.key === "j") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const handleOpenChange = (value: boolean) => {
    setOpen(value);
    if (!value) setQuery("");
  };

  const { setOpenMobile } = useSidebar();
  const question = query.trim();
  // Страница не меняется, поэтому шторку меню на телефоне закрываем сами: иначе она заслонит Leo.
  const handleAsk = () => {
    handleOpenChange(false);
    setOpenMobile(false);
    askLeo(question);
  };

  const handleSelect = (item: SearchItem) => {
    if (item.disabled) return;
    handleOpenChange(false);
    if (item.newTab) {
      window.open(item.url, "_blank", "noopener,noreferrer");
    } else {
      router.push(item.url);
    }
  };

  const renderGroups = (items: SearchItem[]) =>
    groupBy(items).map(({ group, items: groupItems }, index) => (
      <React.Fragment key={group}>
        {index > 0 && <CommandSeparator />}
        <CommandGroup heading={group}>
          {groupItems.map((item) => (
            <CommandItem
              disabled={item.disabled}
              key={`${group}-${item.id}`}
              value={`${item.group} ${item.label}`}
              onSelect={() => handleSelect(item)}
            >
              <span className="flex min-w-0 items-center gap-2">
                {item.icon && <item.icon />}
                <span className="truncate">{item.label}</span>
              </span>
            </CommandItem>
          ))}
        </CommandGroup>
      </React.Fragment>
    ));

  return (
    <>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            variant="outline"
            tooltip={t("search.label")}
            aria-label={t("search.label")}
            aria-keyshortcuts="Meta+K Control+K Meta+J Control+J"
            onClick={() => handleOpenChange(true)}
            className="text-muted-foreground"
          >
            <Search />
            <span className="flex-1">{t("search.placeholder")}</span>
            <Kbd className="group-data-[collapsible=icon]:hidden">⌘K</Kbd>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
      <CommandDialog open={open} onOpenChange={handleOpenChange}>
        <Command>
          <CommandInput placeholder={t("search.placeholder")} value={query} onValueChange={setQuery} />
          <CommandList>
            {query ? renderGroups(searchItems) : renderGroups(recommendations)}
            {question ? <AskLeoItem question={question} onAsk={handleAsk} /> : null}
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}
