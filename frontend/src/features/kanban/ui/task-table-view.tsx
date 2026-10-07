"use client";

import { cn } from "cn";
import { useFormatter, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import { BoardActionsButton, BoardContextMenu } from "./board-menu-triggers";
import { useBoard } from "./board-store";
import { DueDate } from "./due-date";
import { JiraKey } from "./jira-key";
import { PriorityBadge } from "./priority-badge";
import { OwnerAvatar, OwnerName } from "./task-owner";
import { labelTone } from "./tones";

/** Every task in one table, in board order, with its column as the status. */
export function TaskTableView() {
  const { board, columnOrder, columnTitle } = useBoard();
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  const format = useFormatter();
  const rows = columnOrder.flatMap((columnId) => (board[columnId] ?? []).map((task) => ({ task, columnId })));

  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <Table>
        <TableHeader className="bg-muted/50">
          <TableRow>
            <TableHead className="ps-4">{t("table.task")}</TableHead>
            <TableHead>{t("table.status")}</TableHead>
            <TableHead>{t("priority.label")}</TableHead>
            <TableHead className="hidden md:table-cell">{t("table.owner")}</TableHead>
            <TableHead className="hidden lg:table-cell">{t("table.label")}</TableHead>
            <TableHead className="hidden xl:table-cell">{t("progress")}</TableHead>
            <TableHead className="hidden sm:table-cell">{t("table.due")}</TableHead>
            <TableHead className="w-12">
              <span className="sr-only">{t("table.actions")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="h-24 text-center text-muted-foreground">
                {t("table.empty")}
              </TableCell>
            </TableRow>
          ) : null}
          {rows.map(({ task, columnId }) => (
            <BoardContextMenu key={task.id} target={{ kind: "task", task, columnId }}>
              <TableRow>
                <TableCell className="max-w-72 ps-4">
                  <span dir="auto" className="block truncate font-medium">
                    {task.title}
                  </span>
                  {task.jira ? <JiraKey issue={task.jira} /> : null}
                </TableCell>
                <TableCell>
                  <Badge variant="outline" dir="auto" className="rounded-md">
                    {columnTitle(columnId)}
                  </Badge>
                </TableCell>
                <TableCell>
                  <PriorityBadge priority={task.priority} />
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  <div className="flex items-center gap-1.5">
                    <OwnerAvatar owner={task.owner} />
                    <OwnerName owner={task.owner} />
                  </div>
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  {task.label ? (
                    <Badge
                      variant="secondary"
                      dir="auto"
                      className={cn("rounded-md border-transparent", labelTone(task.label))}
                    >
                      {task.label}
                    </Badge>
                  ) : null}
                </TableCell>
                <TableCell className="hidden xl:table-cell">
                  {task.progress === null ? null : (
                    <div className="flex w-28 items-center gap-2">
                      <Progress value={task.progress} aria-label={t("table.progressOf", { task: task.title })} />
                      <span className="min-w-8 shrink-0 text-end text-muted-foreground text-xs tabular-nums">
                        {format.number(task.progress / 100, "percent")}
                      </span>
                    </div>
                  )}
                </TableCell>
                <TableCell className="hidden text-muted-foreground sm:table-cell">
                  {task.dueDate ? <DueDate date={task.dueDate} /> : null}
                </TableCell>
                <TableCell>
                  <BoardActionsButton
                    target={{ kind: "task", task, columnId }}
                    label={tc("actionsFor", { name: task.title })}
                  />
                </TableCell>
              </TableRow>
            </BoardContextMenu>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
