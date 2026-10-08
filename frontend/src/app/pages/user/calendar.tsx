import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { Calendar } from "@/features/calendar/ui/calendar";

export function Component() {
  const t = useTranslations("calendar");
  return (
    <>
      <PageMeta title={t("meta.title")} description={t("meta.description")} />
      <Calendar />
    </>
  );
}
