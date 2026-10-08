import { useTranslations } from "use-intl";

import { searchRecord } from "@/app/pages/search-record";
import { PageMeta } from "@/app/root/page-meta";
import { parseTasksQuery } from "@/features/workspace/domain/tasks";
import { TasksScreen } from "@/features/workspace/ui/tasks/tasks-screen";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("workspace");
  const query = parseTasksQuery(searchRecord(useSearchParams()));
  return (
    <>
      <PageMeta title={t("meta.tasks")} />
      <TasksScreen initialQuery={query} />
    </>
  );
}
