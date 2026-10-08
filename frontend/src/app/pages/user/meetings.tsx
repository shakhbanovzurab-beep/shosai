import { useTranslations } from "use-intl";

import { searchValue } from "@/app/pages/search-record";
import { PageMeta } from "@/app/root/page-meta";
import { parseMeetingsView } from "@/features/meetings/domain/meeting";
import { MeetingsScreen } from "@/features/meetings/ui/meetings-screen";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("meetings");
  const params = useSearchParams();
  return (
    <>
      <PageMeta title={t("title")} />
      <MeetingsScreen view={parseMeetingsView(searchValue(params, "view"))} sharedIn={params.get("workspace")} />
    </>
  );
}
