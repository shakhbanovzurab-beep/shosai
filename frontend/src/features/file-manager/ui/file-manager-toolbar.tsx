"use client";

import { ArrowUpDown, Shapes, SlidersHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
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

import { FILE_KINDS, type FileKind } from "../domain/contract";
import { DEFAULT_FILTER, FILE_SHOWS, FILE_SORTS, type FileShow, type FileSort, isFiltered } from "../domain/filters";
import { useFileManager } from "./file-manager-store";

/** What to show (starred, used by Leo, shared in workspaces), which type, and in what order. */
export function FileManagerToolbar() {
  const t = useTranslations("fileManager");
  const { filter, setFilter } = useFileManager();
  const filtered = isFiltered(filter);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant={filtered ? "secondary" : "outline"} size="sm">
          <SlidersHorizontal data-icon="inline-start" />
          {filtered ? t(`show.${filter.show}`) : t("toolbar.filterSort")}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel>{t("toolbar.show")}</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={filter.show}
            onValueChange={(show) => setFilter({ ...filter, show: show as FileShow })}
          >
            {FILE_SHOWS.map((show) => (
              <DropdownMenuRadioItem key={show} value={show}>
                {t(`show.${show}`)}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <Shapes />
              {t("toolbar.fileType")}
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent sideOffset={8}>
              <DropdownMenuRadioGroup
                value={filter.kind}
                onValueChange={(kind) => setFilter({ ...filter, kind: kind as FileKind | "all" })}
              >
                <DropdownMenuRadioItem value="all">{t("toolbar.allTypes")}</DropdownMenuRadioItem>
                {FILE_KINDS.map((kind) => (
                  <DropdownMenuRadioItem key={kind} value={kind}>
                    {t(`kinds.${kind}`)}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <ArrowUpDown />
              {t("toolbar.sortBy")}
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent sideOffset={8}>
              <DropdownMenuRadioGroup
                value={filter.sort}
                onValueChange={(sort) => setFilter({ ...filter, sort: sort as FileSort })}
              >
                {FILE_SORTS.map((sort) => (
                  <DropdownMenuRadioItem key={sort} value={sort}>
                    {t(`sort.${sort}`)}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        </DropdownMenuGroup>
        {filtered ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => setFilter({ ...DEFAULT_FILTER, sort: filter.sort })}>
              {t("section.clearFilters")}
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
