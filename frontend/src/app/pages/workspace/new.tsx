import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { CreateWorkspace } from "@/features/workspace/ui/onboarding/create-workspace";

export function Component() {
  const t = useTranslations("workspace");
  return (
    <>
      <PageMeta title={t("meta.new")} />
      <CreateWorkspace />
    </>
  );
}
