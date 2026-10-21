"use client";

import type { Ref } from "react";

import { cn } from "cn";
import { GripVertical, Plus, Sigma } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { columnSum } from "../domain/board-rules";
import { useBoardSelector, useBoardStickers, useCardIds, useColumn } from "../model/board-hooks";
import { BoardActionsButton, BoardContextMenu } from "./board-menu-triggers";
import { useBoardCommands, useEditable, useManagedByJira } from "./board-store";
import { useVisibleCardIds } from "./filters/use-visible-cards";
import { SWATCHES } from "./palette";

/** Σ одного числового поля в колонке: видимое число и полная фраза для чтения с экрана. */
function ColumnSum({ columnId, stickerId, field }: { columnId: string; stickerId: string; field: string }) {
  const t = useTranslations("kanban");
  const format = useFormatter();
  const title = useColumn(columnId)?.title ?? "";
  // Сумма — по карточкам, которые колонка показывает (под фильтром — по совпавшим).
  const ids = useVisibleCardIds(columnId);
  const total = useBoardSelector((s) => columnSum(ids, s.cards, stickerId));
  if (total === null) return null;
  const sum = format.number(total);
  return (
    <p className="flex min-w-0 items-center gap-1 text-muted-foreground text-xs tabular-nums leading-none">
      <Sigma className="size-3 shrink-0" aria-hidden="true" />
      <span dir="auto" className="truncate" aria-hidden="true">
        {t("column.sum", { field, sum })}
      </span>
      <span className="sr-only">{t("column.sumLabel", { field, column: title, sum })}</span>
    </p>
  );
}

/** Суммы видимых числовых полей доски — только когда такие поля есть. */
export function ColumnSums({ columnId }: { columnId: string }) {
  const stickers = useBoardStickers();
  return (
    <>
      {stickers.map((sticker) =>
        sticker.kind === "number" && sticker.visible ? (
          <ColumnSum key={sticker.id} columnId={columnId} stickerId={sticker.id} field={sticker.name} />
        ) : null,
      )}
    </>
  );
}

/** Точка цвета колонки рядом с названием. */
export function ColumnDot({ columnId }: { columnId: string }) {
  const color = useColumn(columnId)?.color;
  return color ? <span className={cn("size-2 shrink-0 rounded-full", SWATCHES[color].dot)} aria-hidden="true" /> : null;
}

type HeaderProps = { columnId: string; headingId: string; handleRef: Ref<HTMLButtonElement> };

/** Заголовок колонки: ручка перетаскивания, цвет, название, счётчик, суммы, «+» и «⋮». */
export function ColumnHeader({ columnId, headingId, handleRef }: HeaderProps) {
  const { cards } = useBoardCommands();
  const editable = useEditable();
  const managedByJira = useManagedByJira();
  const count = useCardIds(columnId).length;
  const shown = useVisibleCardIds(columnId).length;
  const title = useColumn(columnId)?.title ?? "";
  const t = useTranslations("kanban");
  const tf = useTranslations("kanbanFilters");
  const tc = useTranslations("common");
  return (
    <BoardContextMenu target={{ kind: "column", columnId }}>
      <div data-column-header className="flex items-start justify-between gap-3 px-4 pt-4 pb-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex min-w-0 items-center gap-1.5">
            {managedByJira ? null : (
              <Button
                ref={handleRef}
                variant="ghost"
                size="icon-xs"
                className="-ms-2 cursor-grab text-foreground/70 active:cursor-grabbing"
                aria-label={t("column.drag", { column: title })}
                data-column-handle
              >
                <GripVertical />
              </Button>
            )}
            <ColumnDot columnId={columnId} />
            <h2 id={headingId} dir="auto" className="truncate font-medium text-base leading-none">
              {title}
            </h2>
          </div>
          <p className="text-muted-foreground text-sm tabular-nums leading-none">
            {shown === count ? t("taskCount", { count }) : tf("columnCount", { shown, total: count })}
          </p>
          <ColumnSums columnId={columnId} />
        </div>
        <div className="-me-2 flex items-center gap-0.5 text-muted-foreground">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("column.addTask", { column: title })}
            disabled={!editable}
            onClick={() => cards.addCard(columnId)}
          >
            <Plus />
          </Button>
          <BoardActionsButton target={{ kind: "column", columnId }} label={tc("actionsFor", { name: title })} />
        </div>
      </div>
    </BoardContextMenu>
  );
}
