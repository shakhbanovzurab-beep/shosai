"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { tasksApi } from "../api/tasks-api";
import type { Comment, CommentsPage } from "../domain/tasks-contract";

/*
 * Комментарии задачи для панели: последние — сразу, ранние — по «Показать ранее». Внутри новыми вперёд, как
 * отвечает сервер; панель показывает их старыми сверху.
 */

/** Сколько комментариев панель берёт за раз: последние видны сразу, панель остаётся лёгкой. */
export const COMMENTS_PAGE = 10;

const threads = new Map<string, PollingResource<CommentsPage>>();

export function commentsResource(taskId: string) {
  const existing = threads.get(taskId);
  if (existing) return existing;
  const created = createPollingResource(() => tasksApi.comments(taskId, COMMENTS_PAGE, null));
  threads.set(taskId, created);
  return created;
}

export const useComments = (taskId: string) => usePollingResource(commentsResource(taskId));

/** Без повторов по id: комментарий, пришедший и со страницей, и из своей отправки, — один. */
function merged(newer: Comment[], older: Comment[]) {
  const seen = new Set(newer.map((comment) => comment.id));
  return [...newer, ...older.filter((comment) => !seen.has(comment.id))];
}

/** Дописывает более ранние комментарии к уже загруженным. */
export async function loadEarlierComments(taskId: string) {
  const resource = commentsResource(taskId);
  const state = resource.getSnapshot();
  if (state.status !== "ready" || state.data.next_cursor === null) return;
  const page = await tasksApi.comments(taskId, COMMENTS_PAGE, state.data.next_cursor);
  resource.update((data) => ({ items: merged(data.items, page.items), next_cursor: page.next_cursor }));
}

/** Локальная правка загруженных комментариев. */
export const changeComments = (taskId: string, change: (items: Comment[]) => Comment[]) =>
  commentsResource(taskId).update((data) => ({ ...data, items: change(data.items) }));
