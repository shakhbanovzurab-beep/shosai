"use client";

import type { Plugins, Sensors } from "@dnd-kit/abstract";
import { Accessibility } from "@dnd-kit/dom";
import { type DragEndEvent, type DragOverEvent, type DragStartEvent, KeyboardSensor } from "@dnd-kit/react";
import { isSortable } from "@dnd-kit/react/sortable";
import { useTranslations } from "use-intl";

import type { Subtask } from "../../domain/tasks-contract";
import { keyboardSensor } from "../drag-setup";

/*
 * Перестановка подзадач мышью за ручку и с клавиатуры (пробел, стрелки вверх и вниз): объявления диктора —
 * словами кабинета на языке человека.
 */

export function useSubtaskDrag(subtasks: Subtask[], onMove: (subtaskId: string, to: number) => void) {
  const t = useTranslations("kanbanPanel");
  const titleOf = (id: unknown) => subtasks.find((subtask) => subtask.id === String(id))?.title ?? "";

  const announcements = {
    dragstart: ({ operation: { source } }: DragStartEvent) =>
      source ? t("subtasks.dnd.pickedUp", { item: titleOf(source.id) }) : undefined,
    dragover: ({ operation: { source } }: DragOverEvent) =>
      source && isSortable(source)
        ? t("subtasks.dnd.over", { item: titleOf(source.id), position: source.index + 1, count: subtasks.length })
        : undefined,
    dragend: ({ operation: { source }, canceled }: DragEndEvent) =>
      source ? t(canceled ? "subtasks.dnd.canceled" : "subtasks.dnd.dropped", { item: titleOf(source.id) }) : undefined,
  };

  const plugins = (defaults: Plugins): Plugins => [
    ...defaults.filter((plugin) => plugin !== Accessibility),
    Accessibility.configure({ announcements, screenReaderInstructions: { draggable: t("subtasks.dnd.instructions") } }),
  ];
  const sensors = (defaults: Sensors): Sensors =>
    defaults.map((sensor) => (sensor === KeyboardSensor ? keyboardSensor : sensor));

  function onDragEnd(event: DragEndEvent) {
    const { source } = event.operation;
    if (event.canceled || !source || !isSortable(source)) return;
    if (source.initialIndex !== source.index) onMove(String(source.id), source.index);
  }

  return { plugins, sensors, onDragEnd };
}
