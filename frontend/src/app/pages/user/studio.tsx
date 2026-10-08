import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { STUDIO_TABS, type StudioTab } from "@/features/studio/domain/studio-tabs";
import { StudioScreen } from "@/features/studio/ui/studio-screen";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("studio");
  const tab = useSearchParams().get("tab");
  const initialTab: StudioTab = STUDIO_TABS.find((candidate) => candidate === tab) ?? "context";
  return (
    <>
      <PageMeta title={t("meta.title")} description={t("meta.description")} />
      <StudioScreen initialTab={initialTab} />
    </>
  );
}
