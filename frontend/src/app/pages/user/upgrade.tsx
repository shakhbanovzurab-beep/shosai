import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { UpgradeScreen } from "@/features/upgrade/ui/upgrade-screen";

export function Component() {
  const t = useTranslations("upgrade");
  return (
    <>
      <PageMeta title={t("meta.title")} />
      <UpgradeScreen />
    </>
  );
}
