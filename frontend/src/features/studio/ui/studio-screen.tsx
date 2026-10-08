import { useTranslations } from "use-intl";

import type { StudioTab } from "../domain/studio-tabs";
import { StudioTabs } from "./studio-tabs";

/** Studio: Context, Prompts and Models, opened at the tab the URL asks for. */
export function StudioScreen({ initialTab }: { initialTab: StudioTab }) {
  const t = useTranslations("studio");
  return (
    <div className="flex flex-col gap-6">
      <h1 className="sr-only">{t("meta.title")}</h1>
      <StudioTabs initialTab={initialTab} />
    </div>
  );
}
