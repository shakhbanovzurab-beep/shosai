"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { boardsApi } from "../api/boards-api";
import type { BoardDetail, BoardSummary } from "../domain/boards-contract";

const isSyncing = (board: BoardSummary) => board.jira?.sync_status === "syncing";

/** Все доски; опрашиваются, пока доска Jira синхронизируется, чтобы её статус и счётчик обновлялись сами. */
export const boardsResource = createPollingResource(boardsApi.list, (data) => data.items.some(isSyncing));

export const useBoards = () => usePollingResource(boardsResource);

const details = new Map<string, PollingResource<BoardDetail>>();

/** Одна доска с колонками и карточками; опрашивается, пока синхронизируется с Jira. */
export function boardResource(id: string) {
  const existing = details.get(id);
  if (existing) return existing;
  const created = createPollingResource(
    () => boardsApi.get(id),
    (data) => isSyncing(data.board),
  );
  details.set(id, created);
  return created;
}

export const useBoardDetail = (id: string) => usePollingResource(boardResource(id));

/** Держит список досок в согласии со сводкой, которую только что вернул API. */
export function receiveSummary(summary: BoardSummary) {
  boardsResource.update((data) => {
    const known = data.items.some((b) => b.id === summary.id);
    return {
      ...data,
      items: known ? data.items.map((b) => (b.id === summary.id ? summary : b)) : [...data.items, summary],
    };
  });
}

/** Поправить счётчик задач доски после добавления или удаления. */
export function adjustTaskCount(id: string, by: number) {
  boardsResource.update((data) => ({
    ...data,
    items: data.items.map((b) => (b.id === id ? { ...b, task_count: Math.max(0, b.task_count + by) } : b)),
  }));
}

/** Доски Jira, которые видит подключение; перечитываются при каждом открытии выбора. */
export const jiraBoardsResource = createPollingResource(boardsApi.jiraAvailable);

export const useJiraBoards = () => usePollingResource(jiraBoardsResource);
