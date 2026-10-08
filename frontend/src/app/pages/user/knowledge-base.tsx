import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { KnowledgeBaseScreen } from "@/features/knowledge-base/ui/knowledge-base-screen";
import type { KnowledgeBaseTab } from "@/features/knowledge-base/ui/knowledge-base-tabs";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("knowledgeBase");
  const tab = useSearchParams().get("tab");
  const initialTab: KnowledgeBaseTab = tab === "sources" || tab === "workspaces" ? tab : "files";
  return (
    <>
      <PageMeta title={t("meta.title")} description={t("meta.description")} />
      <KnowledgeBaseScreen initialTab={initialTab} />
    </>
  );
}
