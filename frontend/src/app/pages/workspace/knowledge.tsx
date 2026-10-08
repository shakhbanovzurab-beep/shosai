import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { WorkspaceFilePicker } from "@/features/file-manager/ui/file-picker";
import { TeamKnowledgeScreen } from "@/features/workspace/ui/knowledge/knowledge-screen";

export function Component() {
  const t = useTranslations("workspace");
  return (
    <>
      <PageMeta title={t("meta.knowledge")} />
      <TeamKnowledgeScreen picker={<WorkspaceFilePicker />} />
    </>
  );
}
