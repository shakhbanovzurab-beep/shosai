"use client";

import type { ReactNode } from "react";

import { DragDropProvider, type DragEndEvent, DragOverlay } from "@dnd-kit/react";
import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";

import { moveFile } from "../model/file-actions";
import { filesResource, useFiles } from "../model/files-resource";
import { useFileActionWords } from "../model/words";
import { fileIcons } from "./file-icons";
import { FileManagerProvider, useFileManager } from "./file-manager-store";

const hasFileId = (data: unknown): data is { fileId: string } =>
  typeof data === "object" && data !== null && typeof (data as { fileId?: unknown }).fileId === "string";

const hasFolderId = (data: unknown): data is { folderId: string | null } =>
  typeof data === "object" && data !== null && "folderId" in data;

/** A compact chip that follows the pointer while a file is dragged. */
function DraggedFile({ fileId }: { fileId: string }) {
  const { files } = useFileManager();
  const file = files.find((f) => f.id === fileId);
  if (!file) return null;
  const Icon = fileIcons[file.kind];
  return (
    <div className="flex w-max max-w-64 cursor-grabbing items-center gap-2 rounded-lg border bg-popover px-3 py-2 text-popover-foreground text-sm shadow-lg">
      <Icon className="size-4 shrink-0 text-muted-foreground" />
      <span className="truncate" dir="auto">
        {file.name}
      </span>
    </div>
  );
}

// dnd-kit's screen-reader announcements are still its English defaults: a shared task words them for every board.
function FileManagerDnd({ children }: { children: ReactNode }) {
  const { files, folders } = useFileManager();
  const t = useTranslations("fileManager");
  const words = useFileActionWords();

  function handleDragEnd(event: DragEndEvent) {
    const { source, target } = event.operation;
    if (event.canceled || !source || !target) return;
    const dragged = source.data;
    const dropped = target.data;
    if (!hasFileId(dragged) || !hasFolderId(dropped)) return;
    const file = files.find((f) => f.id === dragged.fileId);
    const folderId = dropped.folderId;
    const folderName = folders.find((f) => f.id === folderId)?.name ?? t("myFiles");
    if (file) void moveFile(file, folderId, folderName, words);
  }

  return (
    <DragDropProvider onDragEnd={handleDragEnd}>
      {children}
      <DragOverlay dropAnimation={null}>
        {(source) => (hasFileId(source.data) ? <DraggedFile fileId={source.data.fileId} /> : null)}
      </DragOverlay>
    </DragDropProvider>
  );
}

function Loading() {
  const t = useTranslations("fileManager");
  return (
    <div className="flex flex-col gap-6">
      <span className="sr-only">{t("loading")}</span>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {["a", "b", "c", "d"].map((key) => (
          <Skeleton key={key} className="h-28 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-72 rounded-xl" />
    </div>
  );
}

/**
 * The account's files for every file-manager page, with drag-to-folder and right-click menus. Lives
 * in the layout so the loaded files and the filter survive navigating into a folder.
 */
export function FileManager({ children }: { children: ReactNode }) {
  const t = useTranslations("fileManager");
  const files = useFiles();
  let body: ReactNode = <Loading />;
  if (files.status === "error")
    body = <LoadError title={t("loadFailed")} message={files.message} onRetry={() => void filesResource.refresh()} />;
  if (files.status === "ready")
    body = (
      <FileManagerProvider data={files.data}>
        <FileManagerDnd>{children}</FileManagerDnd>
      </FileManagerProvider>
    );
  return (
    <div className="flex flex-col gap-6">
      <h1 className="sr-only">{t("myFiles")}</h1>
      {body}
    </div>
  );
}
