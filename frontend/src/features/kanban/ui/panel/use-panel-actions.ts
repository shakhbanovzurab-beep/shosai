"use client";

import { useTranslations } from "use-intl";

import { useMe } from "@/features/identity/model/session-store";

import type { StickerValue } from "../../domain/stickers-contract";
import type { TaskPatch } from "../../domain/tasks-contract";
import { attachmentActions } from "../../model/attachment-actions";
import { useBoardStore } from "../../model/board-hooks";
import { clockActions } from "../../model/clock-actions";
import { commentActions } from "../../model/comment-actions";
import { subtaskActions } from "../../model/subtask-actions";
import { patchTask, setValue } from "../../model/task-actions";

/** Слова, которыми действия задачи называют свои тосты, на языке человека. */
function useTaskWords() {
  return { t: useTranslations("kanban"), ta: useTranslations("kanbanApi"), tc: useTranslations("common") };
}

/** Изменения задачи из панели, привязанные к её доске и словам на языке человека. */
export function usePanelActions(taskId: string) {
  const store = useBoardStore();
  const words = useTaskWords();
  return {
    patch: (patch: TaskPatch) => patchTask(taskId, patch, store, words),
    setValue: (stickerId: string, value: StickerValue | null) => setValue(taskId, stickerId, value, store, words),
  };
}

/** Подзадачи задачи из панели. */
export function useSubtaskActions(taskId: string) {
  return subtaskActions(taskId, useBoardStore(), useTaskWords());
}

/** Комментарии задачи из панели; свой комментарий подписан именем вошедшего человека. */
export function useCommentActions(taskId: string) {
  const me = useMe();
  const author = { user_id: me?.id ?? "", name: me ? (me.display_name ?? me.full_name) : "", is_you: true };
  return commentActions(taskId, author, useBoardStore(), useTaskWords());
}

/** Готовые вложения задачи из панели: обложка, скачивание, удаление. */
export function useAttachmentActions(taskId: string) {
  return attachmentActions(taskId, useBoardStore(), useTaskWords());
}

/** Часы задачи из панели: секундомер, таймер, план и факт. */
export function useClockActions(taskId: string) {
  return clockActions(taskId, useBoardStore(), useTaskWords());
}
