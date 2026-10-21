import { Building2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { Link } from "@/lib/navigation";

import type { TaskSpace } from "../domain/tasks-contract";

/** На карточке задачи пространства: в каком пространстве она живёт, ссылкой на его задачи. */
export function WorkspaceTaskLink({ space }: { space: TaskSpace }) {
  const t = useTranslations("kanban");
  return (
    <Link
      href={`/app/w/${encodeURIComponent(space.workspace_slug)}/tasks`}
      onPointerDown={(event) => event.stopPropagation()}
      className="relative z-10 inline-flex w-fit items-center gap-1 rounded text-muted-foreground text-xs hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
    >
      <Building2 className="size-3" aria-hidden="true" />
      <span dir="auto">{space.workspace_name}</span>
      <span className="sr-only">{t("card.workspaceTask")}</span>
    </Link>
  );
}
