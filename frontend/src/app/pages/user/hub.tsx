import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { HubScreen } from "@/features/hub/ui/hub/hub-screen";
import { useParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("hub");
  const { hubId = "" } = useParams<{ hubId: string }>();
  return (
    <>
      <PageMeta title={t("list.title")} />
      <HubScreen hubId={hubId} />
    </>
  );
}
