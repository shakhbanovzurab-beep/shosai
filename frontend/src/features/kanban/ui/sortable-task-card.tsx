"use client";

import { useSortable } from "@dnd-kit/react/sortable";
import { cn } from "cn";

import { BoardContextMenu } from "./board-menu-triggers";
import { useEditable } from "./board-store";
import { TaskCard } from "./task-card";

/** Карточка на доске: перетаскивается мышью с любого места и с клавиатуры пробелом; открывается её заголовком. */
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
      <div
        ref={ref}
        data-task-id={taskId}
        // Карточки вне экрана не раскладываются: перетаскивание меряет все, и раскладка большой доски дорога.
        className={cn("[contain-intrinsic-size:auto_7rem] [content-visibility:auto]", isDragging && "opacity-30")}
      >
        <TaskCard taskId={taskId} columnId={columnId} />
      </div>
    </BoardContextMenu>
  );
}
