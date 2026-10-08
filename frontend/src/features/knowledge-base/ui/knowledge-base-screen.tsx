import { useTranslations } from "use-intl";

import { type KnowledgeBaseTab, KnowledgeBaseTabs } from "./knowledge-base-tabs";

/** Knowledge: what Leo answers from in Personal, opened at the tab the URL asks for. */
export function KnowledgeBaseScreen({ initialTab }: { initialTab: KnowledgeBaseTab }) {
  const t = useTranslations("knowledgeBase");
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl text-foreground leading-none tracking-tight">{t("heading")}</h1>
        <p className="max-w-3xl text-muted-foreground">{t("intro")}</p>
      </div>
      <KnowledgeBaseTabs initialTab={initialTab} />
    </div>
  );
}
