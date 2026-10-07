"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { kanbanApi } from "../api/kanban-api";
import type { BoardDetail, BoardSummary } from "../domain/board";

const isSyncing = (board: BoardSummary) => board.jira?.sync_status === "syncing";

/** All boards; polls while a Jira board is syncing so its status and count update on their own. */
export const boardsResource = createPollingResource(kanbanApi.listBoards, (data) => data.boards.some(isSyncing));

export const useBoards = () => usePollingResource(boardsResource);

const details = new Map<string, PollingResource<BoardDetail>>();

/** One board's columns and tasks, polled while it syncs with Jira. Re-read whenever it is opened again. */
export function boardResource(id: string) {
  const existing = details.get(id);
  if (existing) return existing;
  const created = createPollingResource(
    () => kanbanApi.getBoard(id),
    (data) => isSyncing(data.board),
  );
  details.set(id, created);
  return created;
}

export const useBoardDetail = (id: string) => usePollingResource(boardResource(id));

/** Keeps the board list in step with a board summary the API just returned. */
export function receiveSummary(summary: BoardSummary) {
  boardsResource.update((data) => {
    const known = data.boards.some((b) => b.id === summary.id);
    return {
      ...data,
      boards: known ? data.boards.map((b) => (b.id === summary.id ? summary : b)) : [...data.boards, summary],
    };
  });
}

/** Adjusts a board's task count after tasks are added or removed. */
export function adjustTaskCount(id: string, by: number) {
  boardsResource.update((data) => ({
    ...data,
    boards: data.boards.map((b) => (b.id === id ? { ...b, task_count: Math.max(0, b.task_count + by) } : b)),
  }));
}

/** The Jira boards the user's Jira connection can see; re-read every time the picker opens. */
export const jiraBoardsResource = createPollingResource(kanbanApi.jiraBoards);

export const useJiraBoards = () => usePollingResource(jiraBoardsResource);
