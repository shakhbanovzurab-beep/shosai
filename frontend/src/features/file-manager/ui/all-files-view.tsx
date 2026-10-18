"use client";

import { useTranslations } from "use-intl";

import type { FileManagerView } from "../domain/files";
import { useFileManager } from "./file-manager-store";
import { FilesSection } from "./files-section";
import { FoldersSection } from "./folders-section";
import { LeoLimitNotice } from "./leo-limit-notice";
import { StorageMeter } from "./storage-meter";

/** The file manager's home: the storage meter, folders, then every file with the folder it lives in. */
export function AllFilesView({ view }: { view: FileManagerView }) {
  const t = useTranslations("fileManager");
  const { files } = useFileManager();

  return (
    <>
      <StorageMeter />
      <LeoLimitNotice />
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
