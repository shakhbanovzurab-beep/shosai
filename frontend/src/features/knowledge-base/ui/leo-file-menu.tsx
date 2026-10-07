"use client";

import type { ReactNode } from "react";

import { useRouter } from "next/navigation";

import { FolderOpen, MoreVertical, RefreshCw, SquareX } from "lucide-react";
import { useTranslations } from "next-intl";

import { contextKit, dropdownKit, type MenuKit } from "@/components/menu-kit";
import { Button } from "@/components/ui/button";
import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import {
  type FileFolder,
  type FileItem,
  folderHref,
  IN_PROGRESS,
  type LeoUse,
  reindexFile,
  rootHref,
  setFileLeo,
  setFolderLeo,
  useFileActionWords,
} from "@/features/file-manager";

type LeoFile = FileItem & { leo: LeoUse };
type MenuProps = { file: LeoFile; folder: FileFolder | undefined };

function LeoFileMenuItems({ kit: K, file, folder }: MenuProps & { kit: MenuKit }) {
  const router = useRouter();
  const t = useTranslations("knowledgeBase");
  const words = useFileActionWords();
  const viaFolder = file.leo.via === "folder" && folder;
  return (
    <>
      <K.Group>
        <K.Item disabled={IN_PROGRESS.has(file.leo.status)} onSelect={() => void reindexFile(file, words)}>
          <RefreshCw />
          {t("menu.reindex")}
        </K.Item>
        <K.Item onSelect={() => router.push(folder ? folderHref(folder.id) : rootHref())}>
          <FolderOpen />
          {t("menu.showInFileManager")}
        </K.Item>
      </K.Group>
      <K.Separator />
      <K.Item onSelect={() => void (viaFolder ? setFolderLeo(folder, false, words) : setFileLeo(file, false, words))}>
        <SquareX />
        {viaFolder ? t("menu.stopFolder", { folder: folder.name }) : t("menu.stopFile")}
      </K.Item>
    </>
  );
}

export function LeoFileActionsButton({ file, folder }: MenuProps) {
  const common = useTranslations("common");
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={common("actionsFor", { name: file.name })}>
          <MoreVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <LeoFileMenuItems kit={dropdownKit} file={file} folder={folder} />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function LeoFileContextMenu({ file, folder, children }: MenuProps & { children: ReactNode }) {
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent className="w-56">
        <LeoFileMenuItems kit={contextKit} file={file} folder={folder} />
      </ContextMenuContent>
    </ContextMenu>
  );
}
