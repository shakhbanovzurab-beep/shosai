"use client";

import { useSortable } from "@dnd-kit/react/sortable";
import { cn } from "cn";

import type { Task } from "../domain/board";
import { BoardContextMenu } from "./board-menu-triggers";
import { useBoard } from "./board-store";
import { TaskCard } from "./task-card";

export function SortableTaskCard({ task, columnId, index }: { task: Task; columnId: string; index: number }) {
  const { editable } = useBoard();
  const { isDragging, ref } = useSortable({
    disabled: !editable,
    id: task.id,
    index,
    type: "task",
    accept: "task",
    group: columnId,
    data: { type: "task", task, columnId },
  });

  return (
    <BoardContextMenu target={{ kind: "task", task, columnId }}>
      <div ref={ref} data-task-id={task.id} className={cn("touch-none", isDragging && "opacity-30")}>
        <TaskCard task={task} columnId={columnId} />
      </div>
    </BoardContextMenu>
  );
}
