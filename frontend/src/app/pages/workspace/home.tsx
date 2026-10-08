import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { TeamHomeScreen } from "@/features/workspace/ui/home/home-screen";

export function Component() {
  const t = useTranslations("workspace");
  return (
    <>
      <PageMeta title={t("meta.home")} />
      <TeamHomeScreen />
    </>
  );
}
