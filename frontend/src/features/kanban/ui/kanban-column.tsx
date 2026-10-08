"use client";

import { useId } from "react";

import { CollisionPriority } from "@dnd-kit/abstract";
import { useDroppable } from "@dnd-kit/react";
import { useSortable } from "@dnd-kit/react/sortable";
import { cn } from "cn";
import { GripVertical, Plus } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import type { Task } from "../domain/board";
import { BoardActionsButton, BoardContextMenu } from "./board-menu-triggers";
import { useBoard } from "./board-store";
import { SortableTaskCard } from "./sortable-task-card";

interface KanbanColumnProps {
  columnId: string;
  index: number;
  tasks: Task[];
}

/**
 * One column. Columns sit in reading order, so in Arabic the next one is to the left; dragging with the
 * keyboard (Space, then the arrow keys) moves by what is on screen, so ArrowLeft heads for the end there.
 */
export function KanbanColumn({ columnId, index, tasks }: KanbanColumnProps) {
  const { columnTitle, actions, editable, managedByJira } = useBoard();
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  const headingId = useId();
  const column = { id: columnId };
  const title = columnTitle(columnId);
  const {
    ref: columnRef,
    handleRef: columnHandleRef,
    isDragging: isColumnDragging,
    isDropTarget: isColumnDropTarget,
  } = useSortable({
    id: `column:${column.id}`,
    index,
    // Jira owns a synced board's columns.
    disabled: managedByJira,
    type: "column",
    accept: "column",
    group: "columns",
    data: { type: "column", columnId: column.id },
  });
  const { ref: taskDropRef, isDropTarget: isTaskDropTarget } = useDroppable({
    id: column.id,
    type: "task-container",
    accept: "task",
    collisionPriority: CollisionPriority.Low,
    data: { type: "task-container", columnId: column.id },
  });

  return (
    <section
      ref={columnRef}
      data-column-id={column.id}
      aria-labelledby={headingId}
      className={cn(
        "flex min-h-0 flex-col rounded-t-xl border bg-muted/50 transition-colors",
        (isColumnDropTarget || isTaskDropTarget) && "bg-muted/70",
        isColumnDragging && "opacity-60",
      )}
    >
      <BoardContextMenu target={{ kind: "column", columnId: column.id }}>
        <div data-column-header className="flex items-start justify-between gap-3 px-4 pt-4 pb-3">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-0.5">
              {managedByJira ? null : (
                <Button
                  ref={columnHandleRef}
                  variant="ghost"
                  size="icon-xs"
                  className="-ms-2 cursor-grab text-foreground/70 active:cursor-grabbing"
                  aria-label={t("column.drag", { column: title })}
                  data-column-handle
                >
                  <GripVertical />
                </Button>
              )}
              <h2 id={headingId} dir="auto" className="truncate font-medium text-base leading-none">
                {title}
              </h2>
            </div>
            <p className="text-muted-foreground text-sm tabular-nums leading-none">
              {t("taskCount", { count: tasks.length })}
            </p>
          </div>
          <div className="-me-2 flex items-center gap-0.5 text-muted-foreground">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("column.addTask", { column: title })}
              disabled={!editable}
              onClick={() => actions.addTask(column.id)}
            >
              <Plus />
            </Button>
            <BoardActionsButton
              target={{ kind: "column", columnId: column.id }}
              label={tc("actionsFor", { name: title })}
            />
          </div>
        </div>
      </BoardContextMenu>

      <div
        ref={taskDropRef}
        className="scrollbar-thin flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-3 pb-3 [scrollbar-color:var(--border)_transparent] [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:w-1"
      >
        {tasks.map((task, taskIndex) => (
          <SortableTaskCard key={task.id} task={task} columnId={column.id} index={taskIndex} />
        ))}
      </div>
    </section>
  );
}
