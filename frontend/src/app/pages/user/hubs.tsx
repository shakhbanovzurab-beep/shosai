import { useTranslations } from "use-intl";

import { searchValue } from "@/app/pages/search-record";
import { PageMeta } from "@/app/root/page-meta";
import { parseHubsFilter } from "@/features/hub/domain/paths";
import { HubsScreen } from "@/features/hub/ui/list/hubs-screen";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("hub");
  const filter = parseHubsFilter(searchValue(useSearchParams(), "show"));
  return (
    <>
      <PageMeta title={t("list.title")} description={t("list.lead")} />
      <HubsScreen filter={filter} />
    </>
  );
}
