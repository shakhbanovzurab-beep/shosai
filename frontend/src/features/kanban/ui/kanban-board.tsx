"use client";

import { useRef } from "react";

import { move } from "@dnd-kit/helpers";
import { DragDropProvider, type DragEndEvent, type DragOverEvent, DragOverlay } from "@dnd-kit/react";
import { isSortable } from "@dnd-kit/react/sortable";

import type { BoardState, Task } from "../domain/board";
import { useBoard } from "./board-store";
import { KanbanColumn } from "./kanban-column";
import { TaskCard } from "./task-card";

type TaskDragData = { type: "task"; task: Task; columnId: string };

function isTaskDragData(value: unknown): value is TaskDragData {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    value.type === "task" &&
    "task" in value &&
    typeof value.task === "object" &&
    value.task !== null &&
    "columnId" in value &&
    typeof value.columnId === "string"
  );
}

/** The columns side by side; tasks drag between them, and on app boards the columns reorder too. */
export function KanbanBoard() {
  const { board, setBoard, columnOrder, setColumnOrder, actions } = useBoard();
  const boardBeforeDrag = useRef<BoardState>(board);
  const orderBeforeDrag = useRef<string[]>(columnOrder);

  function handleDragStart() {
    boardBeforeDrag.current = board;
    orderBeforeDrag.current = columnOrder;
  }

  function handleDragOver(event: DragOverEvent) {
    if (event.operation.source?.type === "task") setBoard((current) => move(current, event));
  }

  function handleDragEnd(event: DragEndEvent) {
    const { source } = event.operation;
    if (!source) return;
    if (event.canceled) {
      if (source.type === "task") setBoard(boardBeforeDrag.current);
      return;
    }
    if (source.type === "task" && isTaskDragData(source.data))
      actions.commitTaskDrop(source.data.task.id, boardBeforeDrag.current);
    if (source.type === "column") {
      const next = move(columnOrder, event);
      setColumnOrder(next);
      actions.commitColumnOrder(next, orderBeforeDrag.current);
    }
  }

  return (
    <DragDropProvider onDragStart={handleDragStart} onDragOver={handleDragOver} onDragEnd={handleDragEnd}>
      <div className="scrollbar-thin min-h-0 min-w-0 flex-1 overflow-x-auto overflow-y-hidden bg-muted/25 px-4 pt-4 pb-0 [scrollbar-color:var(--border)_transparent] lg:px-5 lg:pt-5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:h-1">
        <div
          className="inline-grid h-full min-w-full gap-4"
          style={{ gridTemplateColumns: `repeat(${columnOrder.length}, minmax(20rem, 1fr))` }}
        >
          {columnOrder.map((columnId, index) => (
            <KanbanColumn key={columnId} columnId={columnId} index={index} tasks={board[columnId] ?? []} />
          ))}
        </div>
      </div>
      <DragOverlay dropAnimation={null}>
        {(source) => {
          if (source.type !== "task" || !isTaskDragData(source.data)) return null;
          const columnId = isSortable(source) && typeof source.group === "string" ? source.group : source.data.columnId;
          return <TaskCard task={source.data.task} columnId={columnId} isOverlay />;
        }}
      </DragOverlay>
    </DragDropProvider>
  );
}
