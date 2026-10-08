import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import type { FileManagerView } from "@/features/file-manager/domain/files";
import { AllFilesView } from "@/features/file-manager/ui/all-files-view";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("fileManager");
  const view: FileManagerView = useSearchParams().get("view") === "list" ? "list" : "grid";
  return (
    <>
      <PageMeta title={t("meta.title")} description={t("meta.description")} />
      <AllFilesView view={view} />
    </>
  );
}
