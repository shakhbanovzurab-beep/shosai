import { cn } from "cn";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

import type { ProjectStatus } from "../../domain/contract";

/** A project's status; only an active one draws attention. */
export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  const t = useTranslations("workspaceProjects");
  return (
    <Badge variant={status === "active" ? "secondary" : "outline"} className="font-normal">
      {t(`status.${status}`)}
    </Badge>
  );
}

/** Done out of all tasks, as a thin bar and a count. */
export function ProjectProgress({
  done,
  total,
  percent,
  className,
}: {
  done: number;
  total: number;
  percent: number;
  className?: string;
}) {
  const t = useTranslations("workspaceProjects");
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <Progress value={percent} aria-label={t("progress.label", { done, total })} className="h-1.5" />
      <span className="shrink-0 text-muted-foreground text-xs tabular-nums">
        {total === 0 ? t("progress.none") : t("progress.count", { done, total })}
      </span>
    </div>
  );
}
