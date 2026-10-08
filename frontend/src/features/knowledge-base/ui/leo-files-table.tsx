"use client";

import type { ReactNode } from "react";

import { Folder } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { FileFolder, FileItem, LeoUse } from "@/features/file-manager/domain/contract";
import { fileIcons } from "@/features/file-manager/ui/file-icons";
import { FileShareControl } from "@/features/workspace/ui/personal/file-share-control";
import { formatBytes } from "@/i18n/format-units";

import { fileExtension } from "../model/leo-files";
import { FileStatusCell } from "./file-status";
import { LeoFileActionsButton, LeoFileContextMenu } from "./leo-file-menu";

type LeoFile = FileItem & { leo: LeoUse };

const userText = (chunks: ReactNode) => <bdi>{chunks}</bdi>;

/** The files Leo uses: where each is, how far indexing got, and the workspaces it is shared in. */
export function LeoFilesTable({ files, folders }: { files: LeoFile[]; folders: FileFolder[] }) {
  const t = useTranslations("knowledgeBase");
  const common = useTranslations("common");
  const format = useFormatter();
  const locale = useLocale();
  return (
    <div className="overflow-hidden rounded-xl border">
      <Table>
        <TableHeader className="bg-muted/50">
          <TableRow>
            <TableHead className="ps-4">{common("fields.name")}</TableHead>
            <TableHead>{t("table.status")}</TableHead>
            <TableHead className="hidden text-end md:table-cell">{t("table.chunks")}</TableHead>
            <TableHead className="hidden text-end sm:table-cell">{t("table.size")}</TableHead>
            <TableHead className="hidden lg:table-cell">
              <span className="sr-only">{t("table.workspaces")}</span>
            </TableHead>
            <TableHead className="w-12">
              <span className="sr-only">{t("table.actions")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {files.map((file) => {
            const folder = folders.find((f) => f.id === file.folder_id);
            const Icon = fileIcons[file.kind];
            return (
              <LeoFileContextMenu key={file.id} file={file} folder={folder}>
                <TableRow>
                  <TableCell className="max-w-48 ps-4 sm:max-w-80">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="grid size-8 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
                        <Icon className="size-4" aria-hidden="true" />
                      </div>
                      <div className="flex min-w-0 flex-col">
                        <span className="truncate font-medium" dir="auto">
                          {file.name}
                        </span>
                        <span className="flex min-w-0 items-center gap-1 text-muted-foreground text-xs">
                          {folder ? <Folder className="size-3 shrink-0" aria-hidden="true" /> : null}
                          <span className="truncate">
                            {folder && file.leo.via === "folder"
                              ? t.rich("table.wholeFolder", { folder: folder.name, name: userText })
                              : null}
                            {folder && file.leo.via !== "folder" ? <bdi>{folder.name}</bdi> : null}
                            {folder ? null : fileExtension(file.name)}
                          </span>
                        </span>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <FileStatusCell name={file.name} leo={file.leo} />
                  </TableCell>
                  <TableCell className="hidden text-end tabular-nums md:table-cell">
                    {file.leo.chunk_count === null ? "—" : format.number(file.leo.chunk_count)}
                  </TableCell>
                  <TableCell className="hidden text-end text-muted-foreground tabular-nums sm:table-cell">
                    {formatBytes(locale, file.size_bytes)}
                  </TableCell>
                  <TableCell className="hidden text-end lg:table-cell">
                    <FileShareControl file={file} />
                  </TableCell>
                  <TableCell>
                    <LeoFileActionsButton file={file} folder={folder} />
                  </TableCell>
                </TableRow>
              </LeoFileContextMenu>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
