"use client";

import type { Plugins, Sensors } from "@dnd-kit/abstract";
import { Accessibility } from "@dnd-kit/dom";
import {
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
  KeyboardSensor,
  PointerSensor,
} from "@dnd-kit/react";
import { useTranslations } from "use-intl";

import { locate } from "../domain/board-rules";
import { useBoardStore } from "../model/board-hooks";

/*
 * Перетаскивание доски для клавиатуры и экранного диктора: поднимает пробел (Enter открывает карточку), а
 * объявления и подсказка — словами кабинета на языке человека, а не английскими умолчаниями dnd-kit.
 */

type Source = DragStartEvent["operation"]["source"];

const INTERACTIVE = "input, select, textarea, button, a[href], [contenteditable]:not([contenteditable='false'])";

/**
 * Мышью карточку тянут с любого места: заголовок-кнопка растянут на всю карточку, поэтому он не мешает начать
 * перетаскивание. Остальные кнопки и ссылки карточки работают как обычно.
 */
const pointerSensor = PointerSensor.configure({
  preventActivation: (event) => {
    if (!(event.target instanceof Element)) return false;
    const interactive = event.target.closest(INTERACTIVE);
    return interactive !== null && !interactive.hasAttribute("data-card-open");
  },
});

/** Клавиатура поднимает пробелом: Enter на карточке открывает её, в строке подзадачи — ничего не тащит. */
export const keyboardSensor = KeyboardSensor.configure({
  keyboardCodes: { ...KeyboardSensor.defaults.keyboardCodes, start: ["Space"] },
});

const columnIdOf = (data: unknown) =>
  typeof data === "object" && data !== null && "columnId" in data && typeof data.columnId === "string"
    ? data.columnId
    : "";

export function useDragSetup() {
  const t = useTranslations("kanban");
  const store = useBoardStore();

  const nameOf = (source: NonNullable<Source>) => {
    const s = store.get();
    return source.type === "column"
      ? (s.columns[columnIdOf(source.data)]?.title ?? "")
      : (s.cards[String(source.id)]?.title ?? "");
  };

  const announcements = {
    dragstart: ({ operation: { source } }: DragStartEvent) =>
      source ? t("dnd.pickedUp", { item: nameOf(source) }) : undefined,
    dragover: ({ operation: { source } }: DragOverEvent) => {
      if (!source) return undefined;
      const s = store.get();
      if (source.type === "column") {
        const position = s.columnOrder.indexOf(columnIdOf(source.data)) + 1;
        return t("dnd.columnOver", { item: nameOf(source), position, count: s.columnOrder.length });
      }
      const at = locate(s.cardIds, String(source.id));
      if (!at) return undefined;
      const count = s.cardIds[at.columnId]?.length ?? 0;
      const column = s.columns[at.columnId]?.title ?? "";
      return t("dnd.over", { item: nameOf(source), column, position: at.index + 1, count });
    },
    dragend: ({ operation: { source }, canceled }: DragEndEvent) =>
      source ? t(canceled ? "dnd.canceled" : "dnd.dropped", { item: nameOf(source) }) : undefined,
  };

  const plugins = (defaults: Plugins): Plugins => [
    ...defaults.filter((plugin) => plugin !== Accessibility),
    Accessibility.configure({ announcements, screenReaderInstructions: { draggable: t("dnd.instructions") } }),
  ];
  const sensors = (defaults: Sensors): Sensors =>
    defaults.map((sensor) => {
      if (sensor === PointerSensor) return pointerSensor;
      return sensor === KeyboardSensor ? keyboardSensor : sensor;
    });
  return { plugins, sensors };
}
