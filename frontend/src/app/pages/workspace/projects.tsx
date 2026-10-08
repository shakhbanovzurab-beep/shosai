import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { ProjectsScreen } from "@/features/workspace/ui/projects/projects-screen";

export function Component() {
  const t = useTranslations("workspace");
  return (
    <>
      <PageMeta title={t("meta.projects")} />
      <ProjectsScreen />
    </>
  );
}
