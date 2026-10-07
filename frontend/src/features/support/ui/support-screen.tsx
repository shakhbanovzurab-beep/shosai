import { useTranslations } from "next-intl";

import { SupportView } from "./support-view";

/** Support: your tickets, with the open one beside the list. */
export function SupportScreen() {
  const t = useTranslations("pagesSupport");
  return (
    <div data-content-padding="false">
      <h1 className="sr-only">{t("meta.title")}</h1>
      <SupportView />
    </div>
  );
}
