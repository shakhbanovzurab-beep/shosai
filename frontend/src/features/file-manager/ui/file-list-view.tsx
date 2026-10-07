"use client";

import { useDraggable } from "@dnd-kit/react";
import { cn } from "cn";
import { Star } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatBytes } from "@/i18n/format-units";

import type { FileItem } from "../domain/contract";
import { toggleStar } from "../model/file-actions";
import { useFileActionWords } from "../model/words";
import { ItemActionsButton, ItemContextMenu } from "./file-actions";
import { FileBadges } from "./file-badges";
import { fileIcons } from "./file-icons";
import { useFileManager } from "./file-manager-store";
import { useAgo } from "./use-ago";

function FileRow({ file, folderName }: { file: FileItem; folderName: string | null }) {
  const { ref, isDragging } = useDraggable({ id: `file:${file.id}`, type: "file", data: { fileId: file.id } });
  const FileIcon = fileIcons[file.kind];
  const t = useTranslations("fileManager");
  const locale = useLocale();
  const ago = useAgo();
  const words = useFileActionWords();

  return (
    <ItemContextMenu target={{ kind: "file", file }}>
      <TableRow ref={ref} className={cn("cursor-grab active:cursor-grabbing", isDragging && "opacity-40")}>
        <TableCell className="ps-0">
          <div className="flex min-w-0 items-center gap-3">
            <FileIcon className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span className="max-w-72 truncate font-medium" dir="auto">
              {file.name}
            </span>
            <FileBadges file={file} folderName={folderName} className="hidden items-center gap-1.5 lg:flex" />
          </div>
        </TableCell>
        <TableCell className="hidden text-muted-foreground md:table-cell">{ago(file.modified_at)}</TableCell>
        <TableCell className="hidden text-muted-foreground tabular-nums sm:table-cell">
          {formatBytes(locale, file.size_bytes)}
        </TableCell>
        <TableCell>
          <div className="flex items-center justify-end">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t(file.starred ? "file.unstar" : "file.star", { name: file.name })}
              aria-pressed={file.starred}
              onClick={() => void toggleStar(file, words)}
            >
              <Star className={cn(file.starred && "fill-current")} />
            </Button>
            <ItemActionsButton target={{ kind: "file", file }} />
          </div>
        </TableCell>
      </TableRow>
    </ItemContextMenu>
  );
}

/** `showFolder` labels each file with its folder; pointless inside a folder, where they all share it. */
export function FileListView({ files, showFolder }: { files: FileItem[]; showFolder: boolean }) {
  const t = useTranslations("fileManager");
  const common = useTranslations("common");
  const { folders } = useFileManager();
  const folderName = (file: FileItem) =>
    showFolder ? (folders.find((folder) => folder.id === file.folder_id)?.name ?? null) : null;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="ps-0">{common("fields.name")}</TableHead>
          <TableHead className="hidden md:table-cell">{t("table.modified")}</TableHead>
          <TableHead className="hidden sm:table-cell">{t("table.size")}</TableHead>
          <TableHead className="w-20">
            <span className="sr-only">{t("table.actions")}</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {files.map((file) => (
          <FileRow key={file.id} file={file} folderName={folderName(file)} />
        ))}
      </TableBody>
    </Table>
  );
}
