import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { ResetPanel } from "@/features/identity/ui/reset-panel";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("identityRecovery");
  const token = useSearchParams().get("token") || null;
  return (
    <>
      <PageMeta title={t("reset.metaTitle")} />
      <ResetPanel token={token} />
    </>
  );
}
