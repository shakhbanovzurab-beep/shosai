"use client";

import Link from "next/link";

import { Archive, ArchiveRestore, EllipsisVertical, FolderOpen, Kanban, Pencil, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import type { Hub } from "../../domain/contract";
import { hubPath } from "../../domain/paths";
import { restoreHub } from "../../model/hub-actions";
import { useHubWords } from "../../model/words";
import type { HubDialogKind } from "./hub-dialogs";

/** A hub's actions behind "⋮": always visible, so a phone reaches them without hovering. */
export function HubMenu({
  hub,
  onAction,
  withOpen = false,
  className,
}: {
  hub: Hub;
  onAction: (kind: HubDialogKind, hub: Hub) => void;
  withOpen?: boolean;
  className?: string;
}) {
  const t = useTranslations("hub");
  const common = useTranslations("common");
  const words = useHubWords();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          className={className}
          aria-label={common("actionsFor", { name: hub.name })}
        >
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-48">
        <DropdownMenuGroup>
          {withOpen ? (
            <DropdownMenuItem asChild>
              <Link href={hubPath(hub.id)}>
                <FolderOpen />
                {common("actions.open")}
              </Link>
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem onSelect={() => onAction("rename", hub)}>
            <Pencil />
            {common("actions.renameMenu")}
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onAction("board", hub)}>
            <Kanban />
            {t("list.chooseBoard")}
          </DropdownMenuItem>
          {hub.archived ? (
            <DropdownMenuItem onSelect={() => void restoreHub(words, hub)}>
              <ArchiveRestore />
              {t("list.restore")}
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem onSelect={() => onAction("archive", hub)}>
              <Archive />
              {t("list.archive")}
            </DropdownMenuItem>
          )}
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onSelect={() => onAction("delete", hub)}>
          <Trash2 />
          {common("actions.delete")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
