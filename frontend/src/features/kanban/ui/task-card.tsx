"use client";

import { cn } from "cn";
import { BadgeCheck, CalendarDays, type LucideIcon, MessageSquare, Paperclip } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

import type { Card } from "../domain/tasks-contract";
import { useCard, useColumn } from "../model/board-hooks";
import { BoardActionsButton } from "./board-menu-triggers";
import { DueDate } from "./due-date";
import { JiraKey } from "./jira-key";
import { PriorityBadge } from "./priority-badge";
import { OwnerAvatar, OwnerName } from "./task-owner";
import { WorkspaceTaskLink } from "./workspace-task-link";

/** Счётчик карточки и его слово в каталоге `kanban.card.insights`. */
function Count({ icon: Icon, count, kind }: { icon: LucideIcon; count: number; kind: "attachments" | "comments" }) {
  const t = useTranslations("kanban");
  const format = useFormatter();
  return (
    <span className="flex items-center gap-1.5 text-sm">
      <Icon className="size-3.5" aria-hidden="true" />
      <span aria-hidden="true">{format.number(count)}</span>
      <span className="sr-only">{t(`card.insights.${kind}`, { count })}</span>
    </span>
  );
}

/** Ход подзадач в колонке «в работе». */
function SubtaskProgress({ done, total }: { done: number; total: number }) {
  const t = useTranslations("kanban");
  const format = useFormatter();
  const progress = done / total;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-muted-foreground text-xs">
        <span className="leading-none">{t("progress")}</span>
        <span className="tabular-nums leading-none">{format.number(progress, "percent")}</span>
      </div>
      {/* Общая полоса заполняется слева; отражённая — от начала строки. */}
      <Progress value={progress * 100} aria-label={t("progress")} />
    </div>
  );
}

/** Низ карточки: «Выполнена» в закрытой колонке, иначе счётчики вложений и комментариев. */
function CardFooter({ card, done }: { card: Card; done: boolean }) {
  const t = useTranslations("kanban");
  if (!done && card.comment_count === 0 && card.attachment_count === 0) return null;
  return (
    <>
      <Separator />
      {done ? (
        <div className="flex items-center gap-1 font-medium text-green-700 text-sm dark:text-green-600">
          <BadgeCheck className="size-4" aria-hidden="true" />
          {t("card.completed")}
        </div>
      ) : (
        <div className="flex items-center gap-3 text-muted-foreground text-sm">
          {card.attachment_count > 0 ? (
            <Count icon={Paperclip} count={card.attachment_count} kind="attachments" />
          ) : null}
          {card.comment_count > 0 ? <Count icon={MessageSquare} count={card.comment_count} kind="comments" /> : null}
        </div>
      )}
    </>
  );
}

/** Задача: заголовок и приоритет, затем исполнитель и срок, а в работе — ход подзадач. */
export function TaskCard({
  taskId,
  columnId,
  isOverlay = false,
}: {
  taskId: string;
  columnId: string;
  isOverlay?: boolean;
}) {
  const card = useCard(taskId);
  const kind = useColumn(columnId)?.kind;
  const tc = useTranslations("common");
  if (!card) return null;

  return (
    <article
      className={cn(
        "flex flex-col gap-3 rounded-xl border bg-card p-4 text-card-foreground shadow-xs",
        isOverlay && "w-68 rotate-1 shadow-lg",
      )}
    >
      <div className="flex min-w-0 flex-col gap-1.5">
        <div className="flex items-center gap-2">
          <h3 dir="auto" className="min-w-0 flex-1 truncate font-medium text-sm leading-none">
            {card.title}
          </h3>
          {card.priority ? <PriorityBadge priority={card.priority} /> : null}
          {isOverlay ? null : (
            <BoardActionsButton
              target={{ kind: "task", taskId, columnId }}
              label={tc("actionsFor", { name: card.title })}
              className="-my-1 -me-2 shrink-0 text-muted-foreground"
            />
          )}
        </div>
        {card.jira ? <JiraKey issue={card.jira} /> : null}
        {card.space ? <WorkspaceTaskLink space={card.space} /> : null}
      </div>
      {kind === "in_progress" && card.subtasks_total > 0 ? (
        <SubtaskProgress done={card.subtasks_done} total={card.subtasks_total} />
      ) : null}
      <div className="flex items-center justify-between gap-3">
        <span className="flex min-w-0 items-center gap-1.5">
          <OwnerAvatar owner={card.assignee} />
          <OwnerName owner={card.assignee} className="text-muted-foreground text-sm" />
        </span>
        {card.due_on ? (
          <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
            <span className="truncate text-sm">
              <DueDate date={card.due_on} />
            </span>
            <CalendarDays className="size-3" aria-hidden="true" />
          </span>
        ) : null}
      </div>
      <CardFooter card={card} done={kind === "done"} />
    </article>
  );
}
