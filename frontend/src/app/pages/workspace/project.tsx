import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { WorkspaceFilePicker } from "@/features/file-manager/ui/file-picker";
import { ProjectScreen } from "@/features/workspace/ui/projects/project-screen";
import { useParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("workspace");
  const { id = "" } = useParams<{ id: string }>();
  return (
    <>
      <PageMeta title={t("meta.project")} />
      <ProjectScreen projectId={id} picker={<WorkspaceFilePicker />} />
    </>
  );
}
