"use client";

import { useState } from "react";

import { FileStack, Folder, X } from "lucide-react";
import { useTranslations } from "next-intl";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { filesResource, setFolderLeo, useFileActionWords, useFiles } from "@/features/file-manager";

import { useIndex } from "../model/kb-resources";
import { indexTotals, leoFiles } from "../model/leo-files";
import { ChooseFilesDialog } from "./choose-files-dialog";
import { IndexSummary } from "./index-summary";
import { LeoFilesTable } from "./leo-files-table";
import { UploadDropzone } from "./upload-dropzone";

/** The files Leo uses from File Manager: add more, watch them being read, and stop using any of them. */
export function FilesTab() {
  const t = useTranslations("knowledgeBase");
  const words = useFileActionWords();
  const files = useFiles();
  const index = useIndex();
  const [choosing, setChoosing] = useState(false);

  if (files.status === "error")
    return <LoadError title={t("loadFailed")} message={files.message} onRetry={() => void filesResource.refresh()} />;

  const used = files.status === "ready" ? leoFiles(files.data.files) : [];
  const folders = files.status === "ready" ? files.data.folders : [];
  const leoFolders = folders.filter((f) => f.leo);

  return (
    <div className="flex flex-col gap-6">
      {files.status === "ready" ? (
        <IndexSummary
          totals={{ files: used.length, ...indexTotals(used) }}
          index={index.status === "ready" ? index.data : null}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {["files", "chunks", "processing", "embeddings"].map((key) => (
            <Skeleton key={key} className="h-32 rounded-xl" />
          ))}
        </div>
      )}
      <UploadDropzone onChoose={() => setChoosing(true)} />
      {leoFolders.length > 0 ? (
        <section aria-labelledby="leo-folders-heading" className="flex flex-col gap-3">
          <h2 id="leo-folders-heading" className="font-medium text-lg">
            {t("leoFolders.heading")}
          </h2>
          <ul className="flex flex-wrap gap-2">
            {leoFolders.map((folder) => (
              <li key={folder.id} className="flex items-center gap-2 rounded-lg border bg-card py-1 ps-3 pe-1 text-sm">
                <Folder className="size-4 text-muted-foreground" aria-hidden="true" />
                <bdi>{folder.name}</bdi>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label={t("leoFolders.stop", { folder: folder.name })}
                  onClick={() => void setFolderLeo(folder, false, words)}
                >
                  <X />
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <section aria-labelledby="leo-files-heading" className="flex flex-col gap-3">
        <h2 id="leo-files-heading" className="font-medium text-lg">
          {t("leoFiles.heading")}
        </h2>
        {files.status === "loading" ? <Skeleton className="h-48 rounded-xl" /> : null}
        {files.status === "ready" && used.length === 0 ? (
          <Empty className="border border-dashed">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FileStack />
              </EmptyMedia>
              <EmptyTitle>{t("leoFiles.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{t("leoFiles.emptyDescription")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : null}
        {used.length > 0 ? <LeoFilesTable files={used} folders={folders} /> : null}
      </section>
      <ChooseFilesDialog open={choosing} onOpenChange={setChoosing} />
    </div>
  );
}
