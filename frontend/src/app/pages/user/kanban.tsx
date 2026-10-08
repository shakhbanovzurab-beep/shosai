import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { Kanban } from "@/features/kanban/ui/kanban";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("kanban");
  const board = useSearchParams().get("board");
  return (
    <>
      <PageMeta title={t("meta.title")} description={t("meta.description")} />
      <Kanban boardId={board} />
    </>
  );
}
