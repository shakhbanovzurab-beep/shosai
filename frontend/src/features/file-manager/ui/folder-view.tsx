"use client";

import { useDroppable } from "@dnd-kit/react";
import { cn } from "cn";
import { ArrowLeft, ChevronRight, FolderX } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Link } from "@/lib/navigation";

import type { FileManagerView } from "../domain/files";
import { rootHref } from "../domain/paths";
import { ItemActionsButton } from "./file-actions";
import { useFileManager } from "./file-manager-store";
import { FilesSection } from "./files-section";
import { LeoFileIcon } from "./leo-file-icon";

/** "My files", which takes you back and also accepts a dropped file to move it out of the folder. */
function MyFilesCrumb({ view }: { view: FileManagerView }) {
  const t = useTranslations("fileManager");
  const { ref, isDropTarget } = useDroppable({
    id: "folder:root",
    type: "folder",
    accept: "file",
    data: { folderId: null },
  });

  return (
    <Link
      ref={ref}
      href={rootHref(view)}
      className={cn(
        "-mx-1.5 shrink-0 rounded-md px-1.5 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring",
        isDropTarget && "bg-primary/10 text-foreground ring-2 ring-primary",
      )}
    >
      {t("myFiles")}
    </Link>
  );
}

/** A folder's own page: back to all files, the folder's actions, and only its files. */
export function FolderView({ folderId, view }: { folderId: string; view: FileManagerView }) {
  const t = useTranslations("fileManager");
  const { folders, files } = useFileManager();
  const folder = folders.find((f) => f.id === folderId);

  if (!folder) {
    return (
      <Empty className="min-h-64 border border-dashed">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <FolderX />
          </EmptyMedia>
          <EmptyTitle>{t("folder.notFound")}</EmptyTitle>
          <EmptyDescription>{t("folder.notFoundDescription")}</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button variant="outline" size="sm" asChild>
            <Link href={rootHref(view)}>
              <ArrowLeft data-icon="inline-start" className="rtl:-scale-x-100" />
              {t("folder.backToMyFiles")}
            </Link>
          </Button>
        </EmptyContent>
      </Empty>
    );
  }

  return (
    <FilesSection
      files={files.filter((file) => file.folder_id === folder.id)}
      view={view}
      leading={
        <Button variant="ghost" size="sm" className="-ms-2 shrink-0" asChild>
          <Link href={rootHref(view)}>
            <ArrowLeft data-icon="inline-start" className="rtl:-scale-x-100" />
            {t("folder.back")}
          </Link>
        </Button>
      }
      heading={
        <>
          <MyFilesCrumb view={view} />
          <ChevronRight aria-hidden="true" className="size-4 shrink-0 text-muted-foreground rtl:-scale-x-100" />
          <span className="truncate" dir="auto">
            {folder.name}
          </span>
          {folder.leo ? (
            <Badge variant="secondary" className="ms-1" title={t("folders.leoReadsAll")}>
              <LeoFileIcon />
              Leo
            </Badge>
          ) : null}
          <ItemActionsButton target={{ kind: "folder", folder }} />
        </>
      }
      showFolder={false}
      folderId={folder.id}
      empty={{
        title: t("folder.emptyTitle"),
        description: folder.leo ? t("folder.emptyLeo") : t("folder.empty"),
      }}
    />
  );
}
