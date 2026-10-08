import { useTranslations } from "use-intl";

import { searchRecord } from "@/app/pages/search-record";
import { PageMeta } from "@/app/root/page-meta";
import { parseLibraryQuery } from "@/features/workspace/domain/library";
import { TeamMeetingsScreen } from "@/features/workspace/ui/meetings/meetings-screen";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("workspace");
  const query = parseLibraryQuery(searchRecord(useSearchParams()));
  return (
    <>
      <PageMeta title={t("meta.meetings")} />
      <TeamMeetingsScreen initialQuery={query} />
    </>
  );
}
