"use client";

import { useSortable } from "@dnd-kit/react/sortable";
import { cn } from "cn";

import { BoardContextMenu } from "./board-menu-triggers";
import { useEditable } from "./board-store";
import { TaskCard } from "./task-card";

export function SortableTaskCard({ taskId, columnId, index }: { taskId: string; columnId: string; index: number }) {
  const editable = useEditable();
  const { isDragging, ref } = useSortable({
    disabled: !editable,
    id: taskId,
    index,
    type: "task",
    accept: "task",
    group: columnId,
    data: { type: "task", taskId, columnId },
  });

  return (
    <BoardContextMenu target={{ kind: "task", taskId, columnId }}>
      <div ref={ref} data-task-id={taskId} className={cn(isDragging && "opacity-30")}>
        <TaskCard taskId={taskId} columnId={columnId} />
      </div>
    </BoardContextMenu>
  );
}
