import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { ConnectorConsentDemo } from "@/features/settings/mocks/connector-consent-demo";
import { useSearchParams } from "@/lib/navigation";

/** Заглушка экрана согласия OAuth провайдера, только в разработке. */
export function Component() {
  const t = useTranslations("settingsConnectors");
  const params = useSearchParams();
  return (
    <>
      <PageMeta title={t("consent.metaTitle")} />
      <ConnectorConsentDemo connector={params.get("connector") ?? ""} state={params.get("state") ?? ""} />
    </>
  );
}
