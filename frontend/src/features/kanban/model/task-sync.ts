"use client";

import { toast } from "sonner";

import { cardOf, withCounts } from "../domain/task-rules";
import type { TaskDetail } from "../domain/tasks-contract";
import type { BoardStore } from "./board-store";
import { taskResource } from "./task-resource";
import { type ApiWords, type CommonWords, describeProblem, type KanbanWords } from "./words";

/*
 * Изменение задачи из панели видно сразу и в панели, и на карточке доски (это одна задача). Сбой откатывает только
 * своё изменение — параллельные правки других полей и подзадач остаются — и говорит, почему.
 */

export type TaskWords = { t: KanbanWords; ta: ApiWords; tc: CommonWords };
export type TaskChange = (detail: TaskDetail) => TaskDetail;

const LOCAL = "local:";

/** Id подзадачи или комментария, которые ещё создаются: с ними нельзя ничего делать, пока сервер не ответил. */
export const localId = () => `${LOCAL}${crypto.randomUUID()}`;
export const isLocalId = (id: string) => id.startsWith(LOCAL);

/** Показать задачу после изменения: панель и карточка; счётчики карточки — из списков задачи. */
export function showTask(id: string, store: BoardStore | null, change: TaskChange) {
  const resource = taskResource(id);
  resource.update((detail) => withCounts(change(detail)));
  const state = resource.getSnapshot();
  if (state.status !== "ready" || !store?.get().cards[id]) return;
  const card = cardOf(state.data);
  store.update((s) => ({ ...s, cards: { ...s.cards, [id]: card } }));
}

export function reportFailure(error: unknown, words: TaskWords) {
  toast.error(words.t("errors.saveChange"), { description: describeProblem(error, words.ta) });
}

/** Ответ сервера целиком, но с подзадачами, которые ещё создаются. */
export const freshTask =
  (fresh: TaskDetail): TaskChange =>
  (current) => ({ ...fresh, subtasks: [...fresh.subtasks, ...current.subtasks.filter((s) => isLocalId(s.id))] });

type Change = {
  /** Что видно сразу. */
  apply: TaskChange;
  /** Как убрать только это изменение, если сервер отказал. */
  revert: TaskChange;
  /** Запрос; отвечает поправкой по ответу сервера или null. */
  work: () => Promise<TaskChange | null>;
};

/** Изменить сразу и отправить. */
export async function changeTask(id: string, store: BoardStore | null, words: TaskWords, change: Change) {
  showTask(id, store, change.apply);
  try {
    const settle = await (store ? store.track(change.work()) : change.work());
    if (settle) showTask(id, store, settle);
    return true;
  } catch (error) {
    showTask(id, store, change.revert);
    reportFailure(error, words);
    return false;
  }
}
