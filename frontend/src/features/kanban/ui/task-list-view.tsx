"use client";

import { CalendarDays, Plus } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { useCard, useColumn, useColumnOrder } from "../model/board-hooks";
import { BoardActionsButton, BoardContextMenu } from "./board-menu-triggers";
import { useBoardCommands, useEditable } from "./board-store";
import { DueDate } from "./due-date";
import { useVisibleCardIds } from "./filters/use-visible-cards";
import { JiraKey } from "./jira-key";
import { PriorityBadge } from "./priority-badge";
import { OwnerAvatar, OwnerName } from "./task-owner";

function TaskRow({ taskId, columnId }: { taskId: string; columnId: string }) {
  const tc = useTranslations("common");
  const task = useCard(taskId);
  if (!task) return null;
  return (
    <BoardContextMenu target={{ kind: "task", taskId, columnId }}>
      <li className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-muted/50">
        <div className="min-w-0 flex-1">
          <p className="flex min-w-0 items-center gap-2 font-medium text-sm">
            <span dir="auto" className="truncate">
              {task.title}
            </span>
            {task.jira ? <JiraKey issue={task.jira} /> : null}
          </p>
        </div>
        {task.priority ? <PriorityBadge priority={task.priority} className="hidden sm:inline-flex" /> : null}
        <div className="hidden w-36 items-center gap-1.5 md:flex">
          <OwnerAvatar owner={task.assignee} />
          <OwnerName owner={task.assignee} className="text-muted-foreground text-sm" />
        </div>
        <span className="hidden w-20 items-center justify-end gap-1.5 text-muted-foreground text-sm lg:flex">
          {task.due_on ? (
            <>
              <DueDate date={task.due_on} />
              <CalendarDays className="size-3" aria-hidden="true" />
            </>
          ) : null}
        </span>
        <BoardActionsButton
          target={{ kind: "task", taskId, columnId }}
          label={tc("actionsFor", { name: task.title })}
          className="-me-2 text-muted-foreground"
        />
      </li>
    </BoardContextMenu>
  );
}

function ColumnSection({ columnId }: { columnId: string }) {
  const { cards } = useBoardCommands();
  const editable = useEditable();
  const title = useColumn(columnId)?.title ?? "";
  const taskIds = useVisibleCardIds(columnId);
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  const format = useFormatter();
  return (
    <section aria-label={title} className="overflow-hidden rounded-xl border bg-card">
      <BoardContextMenu target={{ kind: "column", columnId }}>
        <header className="flex items-center justify-between gap-3 border-b bg-muted/50 px-4 py-2">
          <h2 className="flex items-baseline gap-2 font-medium text-sm">
            <span dir="auto">{title}</span>
            <span className="font-normal text-muted-foreground tabular-nums" aria-hidden="true">
              {format.number(taskIds.length)}
            </span>
            <span className="sr-only">{t("taskCount", { count: taskIds.length })}</span>
          </h2>
          <div className="-me-2 flex items-center gap-0.5 text-muted-foreground">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("column.addTask", { column: title })}
              disabled={!editable}
              onClick={() => cards.addCard(columnId)}
            >
              <Plus />
            </Button>
            <BoardActionsButton target={{ kind: "column", columnId }} label={tc("actionsFor", { name: title })} />
          </div>
        </header>
      </BoardContextMenu>
      {taskIds.length > 0 ? (
        <ul className="divide-y">
          {taskIds.map((taskId) => (
            <TaskRow key={taskId} taskId={taskId} columnId={columnId} />
          ))}
        </ul>
      ) : (
        <p className="px-4 py-3 text-muted-foreground text-sm">{t("column.empty", { column: title })}</p>
      )}
    </section>
  );
}

/** Каждая колонка — раздел строк, в порядке доски. */
export function TaskListView() {
  const columnOrder = useColumnOrder();
  return (
    <div className="flex flex-col gap-4">
      {columnOrder.map((columnId) => (
        <ColumnSection key={columnId} columnId={columnId} />
      ))}
    </div>
  );
}
