import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { safeNext } from "@/features/identity/domain/next-path";
import { ForgotPanel } from "@/features/identity/ui/forgot-panel";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("identityRecovery");
  const next = safeNext(useSearchParams().get("next"));
  return (
    <>
      <PageMeta title={t("forgot.metaTitle")} />
      <ForgotPanel next={next} />
    </>
  );
}
