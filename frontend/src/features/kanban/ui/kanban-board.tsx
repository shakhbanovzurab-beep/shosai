"use client";

import { useRef } from "react";

import { move } from "@dnd-kit/helpers";
import { DragDropProvider, type DragEndEvent, type DragOverEvent, DragOverlay } from "@dnd-kit/react";
import { isSortable } from "@dnd-kit/react/sortable";

import { useBoardSelector, useBoardStore, useColumnOrder } from "../model/board-hooks";
import type { BoardSnapshot } from "../model/board-store";
import { AddColumnButton } from "./add-column-button";
import { useBoardCommands, useEditable, useManagedByJira } from "./board-store";
import { useDragSetup } from "./drag-setup";
import { KanbanColumn } from "./kanban-column";
import { DragPreview } from "./task-card";

type CardDragData = { type: "task"; taskId: string; columnId: string };

function isCardDragData(value: unknown): value is CardDragData {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    value.type === "task" &&
    "taskId" in value &&
    typeof value.taskId === "string" &&
    "columnId" in value &&
    typeof value.columnId === "string"
  );
}

const columnIdOf = (value: unknown) =>
  typeof value === "object" && value !== null && "columnId" in value && typeof value.columnId === "string"
    ? value.columnId
    : null;

/** Колонки рядом; карточки перетаскиваются между ними, на доске в приложении переставляются и колонки. */
export function KanbanBoard() {
  const store = useBoardStore();
  const { cards, columns } = useBoardCommands();
  const columnOrder = useColumnOrder();
  const editable = useEditable();
  const managedByJira = useManagedByJira();
  const canAddColumn = editable && !managedByJira;
  // Свёрнутая колонка — узкая полоса; развёрнутая не уже 20rem и не шире экрана телефона.
  const tracks = useBoardSelector((s) =>
    s.columnOrder.map((id) => (s.columns[id]?.collapsed ? "3rem" : "minmax(min(20rem, 85vw), 1fr)")).join(" "),
  );
  const gridTracks = canAddColumn ? `${tracks} 12rem` : tracks;
  const beforeDrag = useRef<BoardSnapshot | null>(null);
  const dragSetup = useDragSetup();

  function handleDragStart() {
    beforeDrag.current = store.get();
  }

  function handleDragOver(event: DragOverEvent) {
    if (event.operation.source?.type === "task") store.update((s) => ({ ...s, cardIds: move(s.cardIds, event) }));
  }

  function handleDragEnd(event: DragEndEvent) {
    const { source } = event.operation;
    const before = beforeDrag.current;
    if (!source || !before) return;
    if (event.canceled) {
      store.update(() => before);
      return;
    }
    if (source.type === "task" && isCardDragData(source.data)) cards.commitDrop(source.data.taskId, before);
    const columnId = columnIdOf(source.data);
    if (source.type === "column" && columnId) {
      store.update((s) => ({ ...s, columnOrder: move(s.columnOrder, event) }));
      columns.commitColumnMove(columnId, before);
    }
  }

  return (
    <DragDropProvider
      plugins={dragSetup.plugins}
      sensors={dragSetup.sensors}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="scrollbar-thin min-h-0 min-w-0 flex-1 overflow-x-auto overflow-y-hidden bg-muted/25 max-sm:snap-x max-sm:snap-mandatory px-4 pt-4 pb-0 [scrollbar-color:var(--border)_transparent] lg:px-5 lg:pt-5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:h-1">
        <div className="inline-grid h-full min-w-full gap-4" style={{ gridTemplateColumns: gridTracks }}>
          {columnOrder.map((columnId, index) => (
            <KanbanColumn key={columnId} columnId={columnId} index={index} />
          ))}
          {canAddColumn ? <AddColumnButton position={columnOrder.length} /> : null}
        </div>
      </div>
      <DragOverlay dropAnimation={null}>
        {(source) => {
          if (source.type !== "task" || !isCardDragData(source.data)) return null;
          const columnId = isSortable(source) && typeof source.group === "string" ? source.group : source.data.columnId;
          return <DragPreview taskId={source.data.taskId} columnId={columnId} />;
        }}
      </DragOverlay>
    </DragDropProvider>
  );
}
