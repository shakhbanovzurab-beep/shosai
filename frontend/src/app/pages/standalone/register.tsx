import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { safeNext } from "@/features/identity/domain/next-path";
import { RegisterPanel } from "@/features/identity/ui/register-panel";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("identityRegistration");
  const next = safeNext(useSearchParams().get("next"));
  return (
    <>
      <PageMeta title={t("metaTitle")} />
      <RegisterPanel next={next} />
    </>
  );
}
