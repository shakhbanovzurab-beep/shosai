"use client";

import { cn } from "cn";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpDown,
  Check,
  Columns3,
  Eraser,
  FoldHorizontal,
  Palette,
  Pencil,
  Plus,
  SquarePlus,
  Trash2,
} from "lucide-react";
import { useTranslations } from "use-intl";

import type { MenuKit } from "@/components/menu-kit";

import { heirOf } from "../domain/board-rules";
import { COLORS } from "../domain/stickers-contract";
import { useBoardSelector, useCardIds, useColumn, useColumnOrder } from "../model/board-hooks";
import { useBoardCommands, useEditable, useManagedByJira } from "./board-store";
import { SWATCHES } from "./palette";

/** Цвет колонки: образцы палитры и «без цвета». На доске Jira это только вид, в Jira он не уходит. */
function ColourItems({ kit: K, columnId }: { kit: MenuKit; columnId: string }) {
  const { lifecycle } = useBoardCommands();
  const current = useColumn(columnId)?.color ?? null;
  const t = useTranslations("kanban");
  return (
    <K.Sub>
      <K.SubTrigger>
        <Palette />
        {t("columnMenu.colour")}
      </K.SubTrigger>
      <K.SubContent className="w-44">
        <K.Item onSelect={() => lifecycle.setColour(columnId, null)}>
          <Check className={current === null ? undefined : "invisible"} />
          {t("colors.none")}
        </K.Item>
        {COLORS.map((color) => (
          <K.Item key={color} onSelect={() => lifecycle.setColour(columnId, color)}>
            <Check className={current === color ? undefined : "invisible"} />
            <span className={cn("size-2.5 rounded-full", SWATCHES[color].dot)} aria-hidden="true" />
            {t(`colors.${color}`)}
          </K.Item>
        ))}
      </K.SubContent>
    </K.Sub>
  );
}

/** Всё, что можно сделать с колонкой, — для меню правой кнопки и для «⋮». */
export function ColumnMenuItems({ kit: K, columnId }: { kit: MenuKit; columnId: string }) {
  const columnOrder = useColumnOrder();
  const editable = useEditable();
  const managedByJira = useManagedByJira();
  const { cards, columns: actions, lifecycle, askNewColumn } = useBoardCommands();
  const collapsed = useColumn(columnId)?.collapsed === true;
  const deletable = useBoardSelector((s) => heirOf(s.columnOrder, s.columns, columnId) !== null);
  const t = useTranslations("kanban");
  const position = columnOrder.indexOf(columnId);
  const tasks = useCardIds(columnId);

  const shared = (
    <>
      <K.Item disabled={!editable} onSelect={() => cards.addCard(columnId)}>
        <Plus />
        {t("addTask")}
      </K.Item>
      <ColourItems kit={K} columnId={columnId} />
      <K.Item onSelect={() => lifecycle.setCollapsed(columnId, !collapsed)}>
        <FoldHorizontal />
        {collapsed ? t("columnMenu.expand") : t("columnMenu.collapse")}
      </K.Item>
    </>
  );
  if (managedByJira)
    return (
      <K.Group>
        {shared}
        <K.Item disabled>
          <Columns3 />
          {t("columnMenu.managedInJira")}
        </K.Item>
      </K.Group>
    );

  return (
    <>
      <K.Group>
        {shared}
        <K.Item onSelect={() => actions.renameColumn(columnId)}>
          <Pencil />
          {t("columnMenu.rename")}
        </K.Item>
        <K.Item disabled={tasks.length < 2} onSelect={() => actions.sortColumn(columnId)}>
          <ArrowUpDown />
          {t("columnMenu.sortByPriority")}
        </K.Item>
        <K.Item onSelect={() => askNewColumn(position + 1)}>
          <SquarePlus />
          {t("columnMenu.addAfter")}
        </K.Item>
      </K.Group>
      <K.Separator />
      {/* Раньше и позже в порядке чтения: стрелки указывают к началу и к концу строки. */}
      <K.Group>
        <K.Item
          disabled={position <= 0}
          onSelect={() => actions.shiftColumn(columnId, -1)}
          data-menu-action="move-earlier"
        >
          <ArrowLeft className="rtl:-scale-x-100" />
          {t("columnMenu.moveEarlier")}
        </K.Item>
        <K.Item
          disabled={position >= columnOrder.length - 1}
          onSelect={() => actions.shiftColumn(columnId, 1)}
          data-menu-action="move-later"
        >
          <ArrowRight className="rtl:-scale-x-100" />
          {t("columnMenu.moveLater")}
        </K.Item>
      </K.Group>
      <K.Separator />
      <K.Group>
        <K.Item variant="destructive" disabled={tasks.length === 0} onSelect={() => actions.clearColumn(columnId)}>
          <Eraser />
          {t("columnMenu.clear")}
        </K.Item>
        <K.Item variant="destructive" disabled={!deletable} onSelect={() => lifecycle.deleteColumn(columnId)}>
          <Trash2 />
          {deletable ? t("columnMenu.delete") : t("columnMenu.lastOfKind")}
        </K.Item>
      </K.Group>
    </>
  );
}
