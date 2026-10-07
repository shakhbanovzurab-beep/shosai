import Link from "next/link";

import { Building2 } from "lucide-react";
import { useTranslations } from "next-intl";

import type { WorkspaceTaskRef } from "../domain/board";

/** On a card that shows a workspace task: which workspace it lives in, linking there. */
export function WorkspaceTaskLink({ task }: { task: WorkspaceTaskRef }) {
  const t = useTranslations("kanban");
  return (
    <Link
      href={task.url}
      onPointerDown={(event) => event.stopPropagation()}
      className="inline-flex w-fit items-center gap-1 rounded text-muted-foreground text-xs hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
    >
      <Building2 className="size-3" aria-hidden="true" />
      <span dir="auto">{task.workspace_name}</span>
      <span className="sr-only">{t("card.workspaceTask")}</span>
    </Link>
  );
}
