"use client";

import type { ReactNode } from "react";

import { MoreVertical } from "lucide-react";
import { useTranslations } from "use-intl";

import { contextKit, dropdownKit } from "@/components/menu-kit";
import { Button } from "@/components/ui/button";
import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

import type { FileFolder, FileItem } from "../domain/contract";
import { FileMenuItems, FolderMenuItems } from "./item-menus";

type Target = { kind: "file"; file: FileItem } | { kind: "folder"; folder: FileFolder };

const items = (target: Target, kit: typeof dropdownKit) =>
  target.kind === "file" ? (
    <FileMenuItems kit={kit} file={target.file} />
  ) : (
    <FolderMenuItems kit={kit} folder={target.folder} />
  );

/** The "⋮" button: the same actions as the right-click menu, for pointer-less and touch users. */
export function ItemActionsButton({ target }: { target: Target }) {
  const common = useTranslations("common");
  const name = target.kind === "file" ? target.file.name : target.folder.name;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={common("actionsFor", { name })}>
          <MoreVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-60" align="end">
        {items(target, dropdownKit)}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Right-click (or long-press) anywhere on `children` to open the item's menu. */
export function ItemContextMenu({ target, children }: { target: Target; children: ReactNode }) {
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent className="w-60">{items(target, contextKit)}</ContextMenuContent>
    </ContextMenu>
  );
}
