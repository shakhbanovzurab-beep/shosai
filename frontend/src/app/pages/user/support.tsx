import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { SupportScreen } from "@/features/support/ui/support-screen";

export function Component() {
  const t = useTranslations("pagesSupport");
  return (
    <>
      <PageMeta title={t("meta.title")} description={t("meta.description")} />
      <SupportScreen />
    </>
  );
}
