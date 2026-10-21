"use client";

import { useFormatter, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import { useBoardSelector, useCard, useColumn } from "../model/board-hooks";
import { BoardActionsButton, BoardContextMenu } from "./board-menu-triggers";
import { DueDate } from "./due-date";
import { JiraKey } from "./jira-key";
import { PriorityBadge } from "./priority-badge";
import { OwnerAvatar, OwnerName } from "./task-owner";

function Row({ taskId, columnId }: { taskId: string; columnId: string }) {
  const task = useCard(taskId);
  const status = useColumn(columnId)?.title ?? "";
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  const format = useFormatter();
  if (!task) return null;
  const progress = task.subtasks_total > 0 ? task.subtasks_done / task.subtasks_total : null;
  return (
    <BoardContextMenu target={{ kind: "task", taskId, columnId }}>
      <TableRow>
        <TableCell className="max-w-72 ps-4">
          <span dir="auto" className="block truncate font-medium">
            {task.title}
          </span>
          {task.jira ? <JiraKey issue={task.jira} /> : null}
        </TableCell>
        <TableCell>
          <Badge variant="outline" dir="auto" className="rounded-md">
            {status}
          </Badge>
        </TableCell>
        <TableCell>{task.priority ? <PriorityBadge priority={task.priority} /> : null}</TableCell>
        <TableCell className="hidden md:table-cell">
          <div className="flex items-center gap-1.5">
            <OwnerAvatar owner={task.assignee} />
            <OwnerName owner={task.assignee} />
          </div>
        </TableCell>
        <TableCell className="hidden xl:table-cell">
          {progress === null ? null : (
            <div className="flex w-28 items-center gap-2">
              <Progress value={progress * 100} aria-label={t("table.progressOf", { task: task.title })} />
              <span className="min-w-8 shrink-0 text-end text-muted-foreground text-xs tabular-nums">
                {format.number(progress, "percent")}
              </span>
            </div>
          )}
        </TableCell>
        <TableCell className="hidden text-muted-foreground sm:table-cell">
          {task.due_on ? <DueDate date={task.due_on} /> : null}
        </TableCell>
        <TableCell>
          <BoardActionsButton
            target={{ kind: "task", taskId, columnId }}
            label={tc("actionsFor", { name: task.title })}
          />
        </TableCell>
      </TableRow>
    </BoardContextMenu>
  );
}

/** Все задачи одной таблицей, в порядке доски; колонка — статус. */
export function TaskTableView() {
  const columnOrder = useBoardSelector((s) => s.columnOrder);
  const cardIds = useBoardSelector((s) => s.cardIds);
  const t = useTranslations("kanban");
  const rows = columnOrder.flatMap((columnId) => (cardIds[columnId] ?? []).map((taskId) => ({ taskId, columnId })));

  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <Table>
        <TableHeader className="bg-muted/50">
          <TableRow>
            <TableHead className="ps-4">{t("table.task")}</TableHead>
            <TableHead>{t("table.status")}</TableHead>
            <TableHead>{t("priority.label")}</TableHead>
            <TableHead className="hidden md:table-cell">{t("table.owner")}</TableHead>
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
              <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                {t("table.empty")}
              </TableCell>
            </TableRow>
          ) : null}
          {rows.map(({ taskId, columnId }) => (
            <Row key={taskId} taskId={taskId} columnId={columnId} />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
