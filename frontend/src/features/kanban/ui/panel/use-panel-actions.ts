"use client";

import { useTranslations } from "use-intl";

import type { StickerValue } from "../../domain/stickers-contract";
import type { TaskPatch } from "../../domain/tasks-contract";
import { useBoardStore } from "../../model/board-hooks";
import { patchTask, setValue } from "../../model/task-actions";

/** Изменения задачи из панели, привязанные к её доске и словам на языке человека. */
export function usePanelActions(taskId: string) {
  const store = useBoardStore();
  const t = useTranslations("kanban");
  const ta = useTranslations("kanbanApi");
  const words = { t, ta };
  return {
    patch: (patch: TaskPatch) => patchTask(taskId, patch, store, words),
    setValue: (stickerId: string, value: StickerValue | null) => setValue(taskId, stickerId, value, store, words),
  };
}
