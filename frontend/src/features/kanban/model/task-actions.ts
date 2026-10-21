"use client";

import { tasksApi } from "../api/tasks-api";
import type { StickerValue } from "../domain/stickers-contract";
import { leoFieldsAfter } from "../domain/task-rules";
import type { TaskDetail, TaskPatch } from "../domain/tasks-contract";
import type { BoardStore } from "./board-store";
import { changeTask, freshTask, type TaskWords } from "./task-sync";

/* Поля и значения задачи из панели: видны сразу в панели и на карточке; сбой возвращает прежнее. */

const assigneeNamed = (name: string | null) => (name === null ? null : { user_id: null, name });

/** Что из задачи затрагивает изменение полей: эти части и возвращаются при отказе. */
function touched(detail: TaskDetail, patch: TaskPatch): Partial<TaskDetail> {
  const { assignee_id: assigneeId, assignee_name: name, ...fields } = patch;
  const keys = Object.keys(fields) as (keyof TaskDetail)[];
  const before: Partial<TaskDetail> = Object.fromEntries(keys.map((key) => [key, detail[key]]));
  return {
    ...before,
    ...(name === undefined && assigneeId === undefined ? {} : { assignee: detail.assignee }),
    leo_fields: detail.leo_fields,
    recurring: detail.recurring,
  };
}

/** Поля задачи по присутствию; метки Лео на изменённых полях уходят сразу. */
export function patchTask(id: string, patch: TaskPatch, store: BoardStore | null, words: TaskWords) {
  const { assignee_id: _id, assignee_name: name, ...fields } = patch;
  let before: Partial<TaskDetail> = {};
  return changeTask(id, store, words, {
    apply: (detail) => {
      before = touched(detail, patch);
      return {
        ...detail,
        ...(fields as Partial<TaskDetail>),
        assignee: name === undefined ? detail.assignee : assigneeNamed(name),
        leo_fields: leoFieldsAfter(detail.leo_fields, patch),
        recurring: patch.recurrence === undefined ? detail.recurring : patch.recurrence !== null,
      };
    },
    revert: (detail) => ({ ...detail, ...before }),
    work: async () => freshTask(await tasksApi.patch(id, patch)),
  });
}

type OtherValue = TaskDetail["other_values"][number];
type ValueBefore = { own: StickerValue | undefined; other: OtherValue | undefined; index: number };

function withValue(detail: TaskDetail, stickerId: string, value: StickerValue | null): TaskDetail {
  const values = { ...detail.values };
  if (value === null) delete values[stickerId];
  else values[stickerId] = value;
  const other_values = detail.other_values
    .map((entry) => (entry.sticker.id === stickerId && value ? { ...entry, value } : entry))
    .filter((entry) => entry.sticker.id !== stickerId || value !== null);
  return { ...detail, values, other_values };
}

/** Вернуть одно значение, как было: остальные поля задачи не трогаются. */
function restoreValue(detail: TaskDetail, stickerId: string, before: ValueBefore): TaskDetail {
  const values = { ...detail.values };
  if (before.own === undefined) delete values[stickerId];
  else values[stickerId] = before.own;
  const other_values = detail.other_values.filter((entry) => entry.sticker.id !== stickerId);
  if (before.other) other_values.splice(before.index, 0, before.other);
  return { ...detail, values, other_values };
}

/** Значение своего поля; null очищает. */
export function setValue(
  id: string,
  stickerId: string,
  value: StickerValue | null,
  store: BoardStore | null,
  words: TaskWords,
) {
  let before: ValueBefore = { own: undefined, other: undefined, index: 0 };
  return changeTask(id, store, words, {
    apply: (detail) => {
      const index = detail.other_values.findIndex((entry) => entry.sticker.id === stickerId);
      before = { own: detail.values[stickerId], other: detail.other_values[index], index: Math.max(0, index) };
      return withValue(detail, stickerId, value);
    },
    revert: (detail) => restoreValue(detail, stickerId, before),
    work: async () => {
      if (value === null) await tasksApi.clearValue(id, stickerId);
      else await tasksApi.putValue(id, stickerId, value);
      return null;
    },
  });
}
