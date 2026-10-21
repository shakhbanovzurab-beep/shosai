"use client";

import { useId, useState } from "react";

import { CollisionPriority } from "@dnd-kit/abstract";
import { useDroppable } from "@dnd-kit/react";
import { useSortable } from "@dnd-kit/react/sortable";
import { cn } from "cn";
import { useTranslations } from "use-intl";

import { useCardIds, useColumn } from "../model/board-hooks";
import { BoardContextMenu } from "./board-menu-triggers";
import { useBoardCommands, useManagedByJira } from "./board-store";
import { ColumnDot, ColumnHeader } from "./column-header";
import { SWATCHES } from "./palette";
import { RevealMore } from "./reveal-more";
import { SortableTaskCard } from "./sortable-task-card";

/** Сколько карточек колонка показывает сразу и добавляет за раз при прокрутке. */
const REVEAL_STEP = 12;

/** Свёрнутая колонка: узкая полоса с названием сверху вниз и счётчиком; по нажатию разворачивается. */
function CollapsedStrip({ columnId }: { columnId: string }) {
  const { lifecycle } = useBoardCommands();
  const title = useColumn(columnId)?.title ?? "";
  const count = useCardIds(columnId).length;
  const t = useTranslations("kanban");
  return (
    <BoardContextMenu target={{ kind: "column", columnId }}>
      <button
        type="button"
        data-column-header
        onClick={() => lifecycle.setCollapsed(columnId, false)}
        aria-label={t("column.expand", { column: title })}
        className="flex min-h-0 flex-1 flex-col items-center gap-2 rounded-t-xl px-1 py-4 text-start hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
      >
        <ColumnDot columnId={columnId} />
        <span className="text-muted-foreground text-xs tabular-nums" aria-hidden="true">
          {count}
        </span>
        <span dir="auto" className="truncate font-medium text-sm [writing-mode:vertical-rl]" aria-hidden="true">
          {title}
        </span>
      </button>
    </BoardContextMenu>
  );
}

/** Пустая колонка говорит об этом спокойно, без лишних кнопок: «+» есть в заголовке. */
function EmptyColumn({ columnId }: { columnId: string }) {
  const t = useTranslations("kanban");
  const title = useColumn(columnId)?.title ?? "";
  return <p className="px-1 py-6 text-center text-muted-foreground text-sm">{t("column.empty", { column: title })}</p>;
}

/**
 * Одна колонка. Колонки идут в порядке чтения, поэтому в арабском следующая — слева; перетаскивание с
 * клавиатуры (пробел, затем стрелки) движется по экрану, так что там ArrowLeft ведёт к концу доски.
 */
export function KanbanColumn({ columnId, index }: { columnId: string; index: number }) {
  const managedByJira = useManagedByJira();
  const taskIds = useCardIds(columnId);
  const head = useColumn(columnId);
  const headingId = useId();
  const {
    ref: columnRef,
    handleRef: columnHandleRef,
    isDragging: isColumnDragging,
    isDropTarget: isColumnDropTarget,
  } = useSortable({
    id: `column:${columnId}`,
    index,
    // Колонки доски Jira — её.
    disabled: managedByJira,
    type: "column",
    accept: "column",
    group: "columns",
    data: { type: "column", columnId },
  });
  const { ref: taskDropRef, isDropTarget: isTaskDropTarget } = useDroppable({
    id: columnId,
    type: "task-container",
    accept: "task",
    collisionPriority: CollisionPriority.Low,
    data: { type: "task-container", columnId },
  });
  const collapsed = head?.collapsed === true;
  // Длинная колонка показывает карточки порциями по мере прокрутки (замер в плане пакета, шаг 4).
  const [shown, setShown] = useState(REVEAL_STEP);
  const revealMore = () => setShown((count) => count + REVEAL_STEP);

  return (
    <section
      ref={columnRef}
      data-column-id={columnId}
      data-collapsed={collapsed || undefined}
      aria-labelledby={collapsed ? undefined : headingId}
      aria-label={collapsed ? head?.title : undefined}
      className={cn(
        "flex min-h-0 flex-col rounded-t-xl border bg-muted/50 transition-colors max-sm:snap-start",
        head?.color && cn("border-t-2", SWATCHES[head.color].rule),
        (isColumnDropTarget || isTaskDropTarget) && "bg-muted/70",
        isColumnDragging && "opacity-60",
      )}
    >
      {collapsed ? (
        <div ref={taskDropRef} className="flex min-h-0 flex-1 flex-col">
          <CollapsedStrip columnId={columnId} />
        </div>
      ) : (
        <>
          <ColumnHeader columnId={columnId} headingId={headingId} handleRef={columnHandleRef} />
          <div
            ref={taskDropRef}
            className="scrollbar-thin flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-3 pb-3 [scrollbar-color:var(--border)_transparent] [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:w-1"
          >
            {taskIds.slice(0, shown).map((taskId, taskIndex) => (
              <SortableTaskCard key={taskId} taskId={taskId} columnId={columnId} index={taskIndex} />
            ))}
            {taskIds.length > shown ? <RevealMore onReveal={revealMore} /> : null}
            {taskIds.length === 0 ? <EmptyColumn columnId={columnId} /> : null}
          </div>
        </>
      )}
    </section>
  );
}
