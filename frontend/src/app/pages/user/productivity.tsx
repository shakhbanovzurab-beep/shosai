import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { ProductivityScreen } from "@/features/productivity/ui/productivity-screen";

export function Component() {
  const t = useTranslations("productivity");
  return (
    <>
      <PageMeta title={t("meta.title")} description={t("meta.description")} />
      <ProductivityScreen />
    </>
  );
}
