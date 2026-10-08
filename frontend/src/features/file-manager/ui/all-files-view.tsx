"use client";

import { useTranslations } from "use-intl";

import type { FileManagerView } from "../domain/files";
import { useFileManager } from "./file-manager-store";
import { FilesSection } from "./files-section";
import { FoldersSection } from "./folders-section";

/** The file manager's home: folders on top, then every file with the folder it lives in. */
export function AllFilesView({ view }: { view: FileManagerView }) {
  const t = useTranslations("fileManager");
  const { files } = useFileManager();

  return (
    <>
      <FoldersSection view={view} />
      <FilesSection
        files={files}
        view={view}
        heading={t("allFiles.heading")}
        showFolder
        folderId={null}
        empty={{
          title: t("allFiles.emptyTitle"),
          description: t("allFiles.emptyDescription"),
        }}
      />
    </>
  );
}
