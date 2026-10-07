"use client";

import { ArrowLeft, ArrowRight, ArrowUpDown, Columns3, Eraser, Pencil, Plus } from "lucide-react";
import { useTranslations } from "next-intl";

import type { MenuKit } from "@/components/menu-kit";

import { useBoard } from "./board-store";

/** Everything you can do to a column, for either the right-click menu or the "⋮" dropdown. */
export function ColumnMenuItems({ kit: K, columnId }: { kit: MenuKit; columnId: string }) {
  const { board, columnOrder, actions, editable, managedByJira } = useBoard();
  const t = useTranslations("kanban");
  const position = columnOrder.indexOf(columnId);
  const tasks = board[columnId] ?? [];

  const addTask = (
    <K.Item disabled={!editable} onSelect={() => actions.addTask(columnId)}>
      <Plus />
      {t("addTask")}
    </K.Item>
  );
  if (managedByJira)
    return (
      <K.Group>
        {addTask}
        <K.Item disabled>
          <Columns3 />
          {t("columnMenu.managedInJira")}
        </K.Item>
      </K.Group>
    );

  return (
    <>
      <K.Group>
        {addTask}
        <K.Item onSelect={() => actions.renameColumn(columnId)}>
          <Pencil />
          {t("columnMenu.rename")}
        </K.Item>
        <K.Item disabled={tasks.length < 2} onSelect={() => actions.sortColumn(columnId)}>
          <ArrowUpDown />
          {t("columnMenu.sortByPriority")}
        </K.Item>
      </K.Group>
      <K.Separator />
      {/* Earlier and later in reading order: the arrows point to the start and the end of the line. */}
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
      </K.Group>
    </>
  );
}
