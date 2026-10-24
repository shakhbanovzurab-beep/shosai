import { useTranslations } from "use-intl";

import { Skeleton } from "@/components/ui/skeleton";

/** Заготовка разговора, пока панель читает последний тред пространства: вопрос справа, ответ слева. */
export function LeoConversationLoading() {
  const t = useTranslations("leo");
  return (
    <div className="flex flex-1 flex-col gap-4 px-4 py-5" role="status" aria-label={t("panel.loading")}>
      <Skeleton className="ms-auto h-9 w-2/3 rounded-2xl" />
      <Skeleton className="h-20 w-5/6 rounded-2xl" />
      <Skeleton className="ms-auto h-9 w-1/2 rounded-2xl" />
    </div>
  );
}
