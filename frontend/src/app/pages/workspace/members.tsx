import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { MembersScreen } from "@/features/workspace/ui/members/members-screen";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("workspace");
  const initialTab = useSearchParams().get("tab") === "teams" ? "teams" : "members";
  return (
    <>
      <PageMeta title={t("meta.members")} />
      <MembersScreen initialTab={initialTab} />
    </>
  );
}
