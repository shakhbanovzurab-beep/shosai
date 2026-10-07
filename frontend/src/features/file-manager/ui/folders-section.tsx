"use client";

import { Folder, FolderPlus } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

import { type FileManagerView, folderStats } from "../domain/files";
import { useFileManager } from "./file-manager-store";
import { FolderCard } from "./folder-card";

export function FoldersSection({ view }: { view: FileManagerView }) {
  const t = useTranslations("fileManager");
  const format = useFormatter();
  const { folders, files, actions } = useFileManager();

  return (
    <section className="flex flex-col gap-2" aria-labelledby="folders-heading">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-baseline gap-2">
          <h2 id="folders-heading" className="font-medium text-lg">
            {t("folders.heading")}
          </h2>
          <span className="text-muted-foreground text-sm tabular-nums">{format.number(folders.length)}</span>
        </div>
        <Button variant="outline" size="sm" onClick={actions.newFolder}>
          <FolderPlus data-icon="inline-start" />
          {t("folders.new")}
        </Button>
      </div>
      {folders.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {folders.map((folder) => (
            <FolderCard key={folder.id} folder={folder} stats={folderStats(folder, files)} view={view} />
          ))}
        </div>
      ) : (
        <Empty className="min-h-32">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Folder />
            </EmptyMedia>
            <EmptyTitle>{t("folders.emptyTitle")}</EmptyTitle>
            <EmptyDescription>{t("folders.emptyDescription")}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}
    </section>
  );
}
