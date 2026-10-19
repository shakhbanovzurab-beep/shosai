"use client";

import type { ReactNode } from "react";

import { FilterX, FolderOpen, Grid2X2, List } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Link } from "@/lib/navigation";

import type { FileItem } from "../domain/contract";
import type { FileManagerView } from "../domain/files";
import { applyFilter, DEFAULT_FILTER } from "../domain/filters";
import { FileGridView } from "./file-grid-view";
import { FileListView } from "./file-list-view";
import { useFileManager } from "./file-manager-store";
import { FileManagerToolbar } from "./file-manager-toolbar";
import { FileDropZone, UploadButton } from "./upload";
import { UploadTray } from "./upload-tray";

type FilesSectionProps = {
  files: FileItem[];
  view: FileManagerView;
  /** Rendered as the section's labelled heading. */
  heading: ReactNode;
  /** Shown before the heading on the same row, such as a back button. */
  leading?: ReactNode;
  showFolder: boolean;
  /** Where uploads go: the folder being shown, or My files. */
  folderId: string | null;
  empty: { title: string; description: string };
};

function NothingHere({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: typeof FolderOpen;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <Empty className="min-h-48 border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
      {action ? <EmptyContent>{action}</EmptyContent> : null}
    </Empty>
  );
}

/** A heading row with filter, view toggle and upload, then the files as a grid or a table. Files dropped here upload. */
export function FilesSection({ files, view, heading, leading, showFolder, folderId, empty }: FilesSectionProps) {
  const t = useTranslations("fileManager");
  const format = useFormatter();
  const { filter, setFilter, sharedIn } = useFileManager();
  const shared = new Set(files.filter((f) => sharedIn(f.id).length > 0).map((f) => f.id));
  const shown = applyFilter(files, filter, shared);

  return (
    <FileDropZone folderId={folderId}>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 items-center gap-2">
          {leading}
          <h2 className="flex min-w-0 items-center gap-1 font-medium text-lg">{heading}</h2>
          <span className="text-muted-foreground text-sm tabular-nums">{format.number(shown.length)}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <FileManagerToolbar />
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            spacing={0}
            value={view}
            aria-label={t("section.view")}
          >
            <ToggleGroupItem value="grid" asChild>
              <Link href="?view=grid" prefetch={false} replace scroll={false}>
                <Grid2X2 />
                {t("section.grid")}
              </Link>
            </ToggleGroupItem>
            <ToggleGroupItem value="list" asChild>
              <Link href="?view=list" prefetch={false} replace scroll={false}>
                <List />
                {t("section.list")}
              </Link>
            </ToggleGroupItem>
          </ToggleGroup>
          <UploadButton folderId={folderId} />
        </div>
      </div>
      <UploadTray />
      {files.length === 0 ? <NothingHere icon={FolderOpen} {...empty} /> : null}
      {files.length > 0 && shown.length === 0 ? (
        <NothingHere
          icon={FilterX}
          title={t("section.noMatch")}
          description={t("section.noMatchDescription")}
          action={
            <Button variant="outline" size="sm" onClick={() => setFilter({ ...DEFAULT_FILTER, sort: filter.sort })}>
              {t("section.clearFilters")}
            </Button>
          }
        />
      ) : null}
      {shown.length > 0 && view === "list" ? <FileListView files={shown} showFolder={showFolder} /> : null}
      {shown.length > 0 && view === "grid" ? <FileGridView files={shown} showFolder={showFolder} /> : null}
    </FileDropZone>
  );
}
