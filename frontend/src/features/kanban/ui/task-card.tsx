"use client";

import { cn } from "cn";
import { BadgeCheck, CalendarDays, FileText, type LucideIcon, MessageSquare, Paperclip } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

import type { Task, TaskInsight, TaskInsightLabel } from "../domain/board";
import { BoardActionsButton } from "./board-menu-triggers";
import { useBoard } from "./board-store";
import { DueDate } from "./due-date";
import { JiraKey } from "./jira-key";
import { PriorityBadge } from "./priority-badge";
import { OwnerAvatar, OwnerName } from "./task-owner";
import { labelTone } from "./tones";
import { WorkspaceTaskLink } from "./workspace-task-link";

/** Each insight's icon and its key in the `kanban.card.insights` catalog. */
const taskInsights: Record<TaskInsightLabel, { icon: LucideIcon; key: "attachments" | "comments" | "documents" }> = {
  Attachments: { icon: Paperclip, key: "attachments" },
  Comments: { icon: MessageSquare, key: "comments" },
  Documents: { icon: FileText, key: "documents" },
};

function InsightCount({ insight }: { insight: TaskInsight }) {
  const t = useTranslations("kanban");
  const format = useFormatter();
  const { icon: Icon, key } = taskInsights[insight.label];
  return (
    <span className="flex items-center gap-1.5 text-sm">
      <Icon className="size-3.5" aria-hidden="true" />
      <span aria-hidden="true">{format.number(insight.count)}</span>
      <span className="sr-only">{t(`card.insights.${key}`, { count: insight.count })}</span>
    </span>
  );
}

function LabelBadge({ label }: { label: string }) {
  return (
    <Badge
      variant="secondary"
      dir="auto"
      className={cn("rounded-md border-transparent px-2 font-medium", labelTone(label))}
    >
      {label}
    </Badge>
  );
}

/** The due date when there is one, otherwise the label. */
function DueOrLabel({ task }: { task: Task }) {
  if (task.dueDate)
    return (
      <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
        <span className="truncate text-sm">
          <DueDate date={task.dueDate} />
        </span>
        <CalendarDays className="size-3" aria-hidden="true" />
      </span>
    );
  // A workspace card already names its workspace above; the label would repeat it.
  return task.label && !task.workspace ? <LabelBadge label={task.label} /> : null;
}

/** A task: title and priority, then owner and due date, or progress details while it's in progress. */
export function TaskCard({ task, columnId, isOverlay = false }: { task: Task; columnId: string; isOverlay?: boolean }) {
  const { columnKind } = useBoard();
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  const format = useFormatter();
  const kind = columnKind(columnId);
  const isDone = kind === "done";
  const showDetails = kind === "in_progress" && task.progress !== null;
  const source = task.workspace?.source;
  const owner = (
    <span className="flex min-w-0 items-center gap-1.5">
      <OwnerAvatar owner={task.owner} />
      <OwnerName owner={task.owner} className="text-muted-foreground text-sm" />
    </span>
  );

  return (
    <article
      className={cn(
        "flex flex-col gap-3 rounded-xl border bg-card p-4 text-card-foreground shadow-xs",
        isOverlay && "w-68 rotate-1 shadow-lg",
      )}
    >
      <div className="min-w-0 space-y-1.5">
        <div className="flex items-center gap-2">
          <h3 dir="auto" className="min-w-0 flex-1 truncate font-medium text-sm leading-none">
            {task.title}
          </h3>
          <PriorityBadge priority={task.priority} />
          {isOverlay ? null : (
            <BoardActionsButton
              target={{ kind: "task", task, columnId }}
              label={tc("actionsFor", { name: task.title })}
              className="-my-1 -me-2 shrink-0 text-muted-foreground"
            />
          )}
        </div>
        {task.jira ? <JiraKey issue={task.jira} /> : null}
        {task.workspace ? <WorkspaceTaskLink task={task.workspace} /> : null}
        {source ? (
          <p className="line-clamp-2 text-muted-foreground text-sm leading-5">{t("card.fromSource", { source })}</p>
        ) : null}
        {task.description ? (
          <p dir="auto" className="line-clamp-2 text-muted-foreground text-sm leading-5">
            {task.description}
          </p>
        ) : null}
      </div>

      {showDetails ? (
        <div className="flex flex-col gap-3">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-muted-foreground text-xs">
              <span className="leading-none">{t("progress")}</span>
              <span className="tabular-nums leading-none">{format.number((task.progress ?? 0) / 100, "percent")}</span>
            </div>
            {/* The shared bar fills from the left; mirrored, it fills from the start of the line. */}
            <Progress value={task.progress} aria-label={t("progress")} />
          </div>
          <div className="flex items-center justify-between gap-3">
            {owner}
            {task.label ? <LabelBadge label={task.label} /> : null}
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3">
          {owner}
          <DueOrLabel task={task} />
        </div>
      )}

      {isDone || task.insights.length > 0 ? (
        <>
          <Separator />
          {isDone ? (
            <div className="flex items-center gap-1 font-medium text-green-700 text-sm dark:text-green-600">
              <BadgeCheck className="size-4" aria-hidden="true" />
              {t("card.completed")}
            </div>
          ) : (
            <div className="flex items-center gap-3 text-muted-foreground text-sm">
              {task.insights.map((insight) => (
                <InsightCount key={insight.label} insight={insight} />
              ))}
            </div>
          )}
        </>
      ) : null}
    </article>
  );
}
