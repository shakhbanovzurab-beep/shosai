"use client";

import { tasksApi } from "../api/tasks-api";
import { movedTo } from "../domain/task-rules";
import type { Subtask, TaskDetail } from "../domain/tasks-contract";
import type { BoardStore } from "./board-store";
import { taskResource } from "./task-resource";
import { changeTask, isLocalId, localId, reportFailure, showTask, type TaskChange, type TaskWords } from "./task-sync";
import { withUndo } from "./undo";

/*
 * Подзадачи из панели: добавить, отметить, переименовать, переставить, удалить с Undo. Прогресс карточки идёт за
 * ними сразу (`showTask` пересчитывает счётчики).
 */

type SubtaskEdit = { done?: boolean; title?: string };

const subtasksOf = (taskId: string) => {
  const state = taskResource(taskId).getSnapshot();
  return state.status === "ready" ? state.data.subtasks : [];
};

/** Что из подзадачи меняет правка: это и возвращается при отказе. */
const previous = (before: Subtask, patch: SubtaskEdit): Partial<Subtask> => ({
  ...(patch.done === undefined ? {} : { done: before.done }),
  ...(patch.title === undefined ? {} : { title: before.title }),
});

const withSubtasks = (detail: TaskDetail, change: (list: Subtask[]) => Subtask[]) => ({
  ...detail,
  subtasks: change(detail.subtasks),
});

const replaced =
  (subtask: Subtask): TaskChange =>
  (detail) =>
    withSubtasks(detail, (list) => list.map((item) => (item.id === subtask.id ? subtask : item)));

/** Созданная подзадача встаёт на место своей временной строки; если ответ задачи её уже принёс — строка уходит. */
const created =
  (local: string, subtask: Subtask): TaskChange =>
  (detail) =>
    withSubtasks(detail, (list) => {
      if (list.some((item) => item.id === subtask.id)) return list.filter((item) => item.id !== local);
      return list.some((item) => item.id === local)
        ? list.map((item) => (item.id === local ? subtask : item))
        : [...list, subtask];
    });

export function subtaskActions(taskId: string, store: BoardStore | null, words: TaskWords) {
  const change = (parts: Parameters<typeof changeTask>[3]) => changeTask(taskId, store, words, parts);

  return {
    add(title: string) {
      const local: Subtask = { id: localId(), title, done: false };
      return change({
        apply: (detail) => withSubtasks(detail, (list) => [...list, local]),
        revert: (detail) => withSubtasks(detail, (list) => list.filter((item) => item.id !== local.id)),
        work: async () => created(local.id, await tasksApi.addSubtask(taskId, { title })),
      });
    },
    update(subtaskId: string, patch: SubtaskEdit) {
      const before = subtasksOf(taskId).find((item) => item.id === subtaskId);
      if (!before || isLocalId(subtaskId)) return Promise.resolve(false);
      return change({
        apply: replaced({ ...before, ...patch }),
        revert: (detail) =>
          withSubtasks(detail, (list) =>
            list.map((item) => (item.id === subtaskId ? { ...item, ...previous(before, patch) } : item)),
          ),
        work: async () => replaced(await tasksApi.patchSubtask(taskId, subtaskId, patch)),
      });
    },
    move(subtaskId: string, to: number) {
      const list = subtasksOf(taskId);
      const from = list.findIndex((item) => item.id === subtaskId);
      if (from < 0 || from === to || isLocalId(subtaskId)) return Promise.resolve(false);
      return change({
        apply: (detail) => withSubtasks(detail, (items) => movedTo(items, subtaskId, to)),
        revert: (detail) => withSubtasks(detail, (items) => movedTo(items, subtaskId, from)),
        work: async () => {
          await tasksApi.patchSubtask(taskId, subtaskId, { position: to });
          return null;
        },
      });
    },
    remove(subtaskId: string, message: string) {
      const list = subtasksOf(taskId);
      const index = list.findIndex((item) => item.id === subtaskId);
      const subtask = list[index];
      if (!subtask || isLocalId(subtaskId)) return;
      const hide = () =>
        showTask(taskId, store, (detail) =>
          withSubtasks(detail, (items) => items.filter((item) => item.id !== subtaskId)),
        );
      const restore = () =>
        showTask(taskId, store, (detail) =>
          withSubtasks(detail, (items) =>
            items.some((item) => item.id === subtaskId) ? items : items.toSpliced(index, 0, subtask),
          ),
        );
      withUndo({
        message,
        undoLabel: words.tc("actions.undo"),
        hide,
        restore,
        commit: () =>
          tasksApi.removeSubtask(taskId, subtaskId).then(
            // Ответ задачи за время Undo мог вернуть строку: удалённая уходит ещё раз.
            hide,
            (error: unknown) => {
              restore();
              reportFailure(error, words);
            },
          ),
      });
    },
  };
}
