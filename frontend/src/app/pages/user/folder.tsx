import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import type { FileManagerView } from "@/features/file-manager/domain/files";
import { FolderView } from "@/features/file-manager/ui/folder-view";
import { useParams, useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("fileManager");
  const { folderId = "" } = useParams<{ folderId: string }>();
  const view: FileManagerView = useSearchParams().get("view") === "list" ? "list" : "grid";
  return (
    <>
      <PageMeta title={t("meta.folderTitle")} />
      <FolderView folderId={folderId} view={view} />
    </>
  );
}
