"use client";

import { toast } from "sonner";

import { tasksApi } from "../api/tasks-api";
import type { StickerValue } from "../domain/stickers-contract";
import { cardOf, leoFieldsAfter } from "../domain/task-rules";
import type { TaskDetail, TaskPatch } from "../domain/tasks-contract";
import type { BoardStore } from "./board-store";
import { taskResource } from "./task-resource";
import { type ApiWords, describeProblem, type KanbanWords } from "./words";

/*
 * Изменения задачи из панели: видны сразу в панели и на карточке доски (это одна задача); сбой возвращает
 * обе и говорит, почему.
 */

export type TaskWords = { t: KanbanWords; ta: ApiWords };

function show(id: string, store: BoardStore | null, change: (detail: TaskDetail) => TaskDetail) {
  const resource = taskResource(id);
  resource.update(change);
  const state = resource.getSnapshot();
  if (state.status !== "ready" || !store?.get().cards[id]) return;
  const card = cardOf(state.data);
  store.update((s) => ({ ...s, cards: { ...s.cards, [id]: card } }));
}

async function attempt(id: string, store: BoardStore | null, words: TaskWords, work: () => Promise<TaskDetail | null>) {
  const resource = taskResource(id);
  const before = resource.getSnapshot();
  try {
    const fresh = await (store ? store.track(work()) : work());
    if (fresh) show(id, store, () => fresh);
    return true;
  } catch (error) {
    if (before.status === "ready") show(id, store, () => before.data);
    toast.error(words.t("errors.saveChange"), { description: describeProblem(error, words.ta) });
    return false;
  }
}

const assigneeNamed = (name: string | null) => (name === null ? null : { user_id: null, name });

/** Поля задачи по присутствию; метки Лео на изменённых полях уходят сразу. */
export function patchTask(id: string, patch: TaskPatch, store: BoardStore | null, words: TaskWords) {
  const { assignee_id: _id, assignee_name: name, ...fields } = patch;
  show(id, store, (detail) => ({
    ...detail,
    ...(fields as Partial<TaskDetail>),
    assignee: name === undefined ? detail.assignee : assigneeNamed(name),
    leo_fields: leoFieldsAfter(detail.leo_fields, patch),
    recurring: patch.recurrence === undefined ? detail.recurring : patch.recurrence !== null,
  }));
  return attempt(id, store, words, () => tasksApi.patch(id, patch));
}

/** Значение своего поля; null очищает. */
export function setValue(
  id: string,
  stickerId: string,
  value: StickerValue | null,
  store: BoardStore | null,
  words: TaskWords,
) {
  show(id, store, (detail) => {
    const values = { ...detail.values };
    if (value === null) delete values[stickerId];
    else values[stickerId] = value;
    const other_values = detail.other_values
      .map((entry) => (entry.sticker.id === stickerId && value ? { ...entry, value } : entry))
      .filter((entry) => entry.sticker.id !== stickerId || value !== null);
    return { ...detail, values, other_values };
  });
  return attempt(id, store, words, async () => {
    if (value === null) await tasksApi.clearValue(id, stickerId);
    else await tasksApi.putValue(id, stickerId, value);
    return null;
  });
}
