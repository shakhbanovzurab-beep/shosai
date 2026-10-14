import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { desktopRequestOf } from "@/features/identity/domain/desktop-link";
import { ConnectPanel } from "@/features/identity/ui/connect-panel";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("identityDesktop");
  const request = desktopRequestOf(useSearchParams());
  return (
    <>
      <PageMeta title={t("metaTitle")} />
      <ConnectPanel request={request} />
    </>
  );
}
