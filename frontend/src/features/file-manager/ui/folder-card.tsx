"use client";

import { useDroppable } from "@dnd-kit/react";
import { cn } from "cn";
import { Clock, Folder, FolderOpen } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatBytes } from "@/i18n/format-units";
import { Link } from "@/lib/navigation";

import type { FileFolder } from "../domain/contract";
import type { FileManagerView } from "../domain/files";
import { folderHref } from "../domain/paths";
import { ItemActionsButton, ItemContextMenu } from "./file-actions";
import { LeoFileIcon } from "./leo-file-icon";
import { useAgo } from "./use-ago";

type FolderCardProps = {
  folder: FileFolder;
  stats: { count: number; bytes: number; updated: string };
  view: FileManagerView;
};

/** A folder you can open on its own page, right-click, and drop files onto; marked when Leo reads it. */
export function FolderCard({ folder, stats, view }: FolderCardProps) {
  const t = useTranslations("fileManager");
  const locale = useLocale();
  const ago = useAgo();
  const { ref, isDropTarget } = useDroppable({
    id: `folder:${folder.id}`,
    type: "folder",
    accept: "file",
    data: { folderId: folder.id },
  });
  const Icon = isDropTarget ? FolderOpen : Folder;
  let note = t("folders.fileCount", { count: stats.count });
  if (isDropTarget) note = folder.leo ? t("folders.dropHereLeo") : t("folders.dropHere");

  return (
    <ItemContextMenu target={{ kind: "folder", folder }}>
      <Card
        ref={ref}
        size="sm"
        className={cn(
          "relative transition-[box-shadow,background-color] has-[[data-open-folder]:focus-visible]:ring-2 has-[[data-open-folder]:focus-visible]:ring-ring",
          isDropTarget && "bg-primary/5 ring-2 ring-primary",
        )}
      >
        <CardHeader>
          <div className="flex min-w-0 items-center gap-2">
            <div
              className={cn(
                "flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground transition-colors",
                isDropTarget && "bg-primary text-primary-foreground",
              )}
            >
              <Icon className="size-4.5" />
            </div>
            <div className="flex min-w-0 flex-col gap-1">
              <CardTitle className="truncate leading-none">
                {/* Stretched over the card, so a click anywhere opens the folder. */}
                <Link
                  href={folderHref(folder.id, view)}
                  data-open-folder
                  dir="auto"
                  className="outline-none after:absolute after:inset-0 after:content-['']"
                >
                  {folder.name}
                </Link>
              </CardTitle>
              <CardDescription className="text-xs">{note}</CardDescription>
            </div>
          </div>
          <CardAction className="relative z-10">
            <ItemActionsButton target={{ kind: "folder", folder }} />
          </CardAction>
        </CardHeader>
        <CardContent className="flex items-center justify-between gap-3 text-muted-foreground text-xs">
          <div className="flex min-w-0 items-center gap-1.5">
            <Clock className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="truncate">{t("folders.updated", { ago: ago(stats.updated) })}</span>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {folder.leo ? (
              <Badge variant="secondary" title={t("folders.leoReadsAll")}>
                <LeoFileIcon />
                Leo
              </Badge>
            ) : null}
            <span className="tabular-nums">{formatBytes(locale, stats.bytes)}</span>
          </div>
        </CardContent>
      </Card>
    </ItemContextMenu>
  );
}
