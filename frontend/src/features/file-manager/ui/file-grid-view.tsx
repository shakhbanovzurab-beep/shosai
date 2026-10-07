"use client";

import type { ReactNode } from "react";

import { useDraggable } from "@dnd-kit/react";
import { cn } from "cn";
import { Star } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatBytes } from "@/i18n/format-units";

import type { FileItem } from "../domain/contract";
import { toggleStar } from "../model/file-actions";
import { useFileActionWords } from "../model/words";
import { ItemActionsButton, ItemContextMenu } from "./file-actions";
import { FileBadges } from "./file-badges";
import { fileIcons } from "./file-icons";
import { useFileManager } from "./file-manager-store";
import { useAgo } from "./use-ago";

const hidden = (chunks: ReactNode) => <span className="sr-only">{chunks}</span>;
const userText = (chunks: ReactNode) => <bdi>{chunks}</bdi>;

function GridFileCard({ file, folderName }: { file: FileItem; folderName: string | null }) {
  const { ref, isDragging } = useDraggable({ id: `file:${file.id}`, type: "file", data: { fileId: file.id } });
  const FileIcon = fileIcons[file.kind];
  const t = useTranslations("fileManager");
  const locale = useLocale();
  const ago = useAgo()(file.modified_at);
  const words = useFileActionWords();

  return (
    <ItemContextMenu target={{ kind: "file", file }}>
      <Card
        ref={ref}
        size="sm"
        className={cn("group/file cursor-grab transition-opacity active:cursor-grabbing", isDragging && "opacity-40")}
      >
        <CardContent>
          <div className="relative flex h-36 items-center justify-center rounded-lg bg-muted/50">
            <FileIcon className="size-12 text-muted-foreground" aria-hidden="true" />
            <FileBadges
              file={file}
              folderName={null}
              className="absolute start-2 top-2 flex max-w-[70%] flex-wrap gap-1"
            />
            <Button
              variant="secondary"
              size="icon-sm"
              className={cn(
                "absolute end-2 top-2 opacity-0 focus-visible:opacity-100 group-hover/file:opacity-100",
                file.starred && "opacity-100",
              )}
              aria-label={t(file.starred ? "file.unstar" : "file.star", { name: file.name })}
              aria-pressed={file.starred}
              onClick={() => void toggleStar(file, words)}
            >
              <Star className={cn(file.starred && "fill-current")} />
            </Button>
            <div className="absolute inset-x-3 bottom-3 flex items-center justify-between gap-3 text-muted-foreground text-xs">
              <span>{t(`kinds.${file.kind}`)}</span>
              <span className="tabular-nums">{formatBytes(locale, file.size_bytes)}</span>
            </div>
          </div>
        </CardContent>
        <CardHeader>
          <CardTitle className="truncate" dir="auto">
            {file.name}
          </CardTitle>
          <CardDescription className="truncate">
            {folderName
              ? t.rich("file.inFolderModified", { folder: folderName, ago, hidden, name: userText })
              : t("file.modified", { ago })}
          </CardDescription>
          <CardAction>
            <ItemActionsButton target={{ kind: "file", file }} />
          </CardAction>
        </CardHeader>
      </Card>
    </ItemContextMenu>
  );
}

/** `showFolder` labels each file with its folder; pointless inside a folder, where they all share it. */
export function FileGridView({ files, showFolder }: { files: FileItem[]; showFolder: boolean }) {
  const { folders } = useFileManager();
  const folderName = (file: FileItem) =>
    showFolder ? (folders.find((folder) => folder.id === file.folder_id)?.name ?? null) : null;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {files.map((file) => (
        <GridFileCard key={file.id} file={file} folderName={folderName(file)} />
      ))}
    </div>
  );
}
