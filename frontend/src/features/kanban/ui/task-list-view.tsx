"use client";

import { CalendarDays, Plus } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

import type { Task } from "../domain/board";
import { BoardActionsButton, BoardContextMenu } from "./board-menu-triggers";
import { useBoard } from "./board-store";
import { DueDate } from "./due-date";
import { JiraKey } from "./jira-key";
import { PriorityBadge } from "./priority-badge";
import { OwnerAvatar, OwnerName } from "./task-owner";

function TaskRow({ task, columnId }: { task: Task; columnId: string }) {
  const tc = useTranslations("common");
  return (
    <BoardContextMenu target={{ kind: "task", task, columnId }}>
      <li className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-muted/50">
        <div className="min-w-0 flex-1">
          <p className="flex min-w-0 items-center gap-2 font-medium text-sm">
            <span dir="auto" className="truncate">
              {task.title}
            </span>
            {task.jira ? <JiraKey issue={task.jira} /> : null}
          </p>
          {task.description ? (
            <p dir="auto" className="truncate text-muted-foreground text-sm">
              {task.description}
            </p>
          ) : null}
        </div>
        <PriorityBadge priority={task.priority} className="hidden sm:inline-flex" />
        <div className="hidden w-36 items-center gap-1.5 md:flex">
          <OwnerAvatar owner={task.owner} />
          <OwnerName owner={task.owner} className="text-muted-foreground text-sm" />
        </div>
        <span className="hidden w-20 items-center justify-end gap-1.5 text-muted-foreground text-sm lg:flex">
          {task.dueDate ? (
            <>
              <DueDate date={task.dueDate} />
              <CalendarDays className="size-3" aria-hidden="true" />
            </>
          ) : null}
        </span>
        <BoardActionsButton
          target={{ kind: "task", task, columnId }}
          label={tc("actionsFor", { name: task.title })}
          className="-me-2 text-muted-foreground"
        />
      </li>
    </BoardContextMenu>
  );
}

/** Every column as a section of rows, in board order. */
export function TaskListView() {
  const { board, columnOrder, columnTitle, actions, editable } = useBoard();
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  const format = useFormatter();

  return (
    <div className="flex flex-col gap-4">
      {columnOrder.map((columnId) => {
        const title = columnTitle(columnId);
        const tasks = board[columnId] ?? [];
        return (
          <section key={columnId} aria-label={title} className="overflow-hidden rounded-xl border bg-card">
            <BoardContextMenu target={{ kind: "column", columnId }}>
              <header className="flex items-center justify-between gap-3 border-b bg-muted/50 px-4 py-2">
                <h2 className="flex items-baseline gap-2 font-medium text-sm">
                  <span dir="auto">{title}</span>
                  <span className="font-normal text-muted-foreground tabular-nums" aria-hidden="true">
                    {format.number(tasks.length)}
                  </span>
                  <span className="sr-only">{t("taskCount", { count: tasks.length })}</span>
                </h2>
                <div className="-me-2 flex items-center gap-0.5 text-muted-foreground">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={t("column.addTask", { column: title })}
                    disabled={!editable}
                    onClick={() => actions.addTask(columnId)}
                  >
                    <Plus />
                  </Button>
                  <BoardActionsButton target={{ kind: "column", columnId }} label={tc("actionsFor", { name: title })} />
                </div>
              </header>
            </BoardContextMenu>
            {tasks.length > 0 ? (
              <ul className="divide-y">
                {tasks.map((task) => (
                  <TaskRow key={task.id} task={task} columnId={columnId} />
                ))}
              </ul>
            ) : (
              <p className="px-4 py-3 text-muted-foreground text-sm">{t("column.empty", { column: title })}</p>
            )}
          </section>
        );
      })}
    </div>
  );
}
