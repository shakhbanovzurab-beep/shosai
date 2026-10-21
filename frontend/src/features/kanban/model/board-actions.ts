"use client";

import { toast } from "sonner";

import { boardsApi } from "../api/boards-api";
import type { BoardCreate, BoardPatch, BoardSummary, JiraConnect } from "../domain/boards-contract";
import { boardResource, boardsResource, receiveSummary } from "./boards-resource";
import { type ApiWords, type BoardWords, describeProblem } from "./words";

/* Действия с досками целиком: создать, подключить доску Jira, переименовать, удалить, синхронизировать, входящие. */

export type BoardsWords = { t: BoardWords; ta: ApiWords };

const failed = (title: string, error: unknown, ta: ApiWords) => {
  toast.error(title, { description: describeProblem(error, ta) });
  return null;
};

/** Создаёт доску; отдаёт её или null, сообщив о сбое. */
export async function createBoard(request: BoardCreate, { t, ta }: BoardsWords): Promise<BoardSummary | null> {
  try {
    const board = await boardsApi.create(request);
    receiveSummary(board);
    return board;
  } catch (error) {
    return failed(t("toasts.createFailed"), error, ta);
  }
}

/** Начинает двустороннюю синхронизацию с доской Jira; новая доска синхронизируется в фоне. */
export async function connectJiraBoard(request: JiraConnect, { t, ta }: BoardsWords): Promise<BoardSummary | null> {
  try {
    const board = await boardsApi.connectJira(request);
    receiveSummary(board);
    return board;
  } catch (error) {
    return failed(t("toasts.connectFailed"), error, ta);
  }
}

export async function updateBoard(id: string, patch: BoardPatch, { t, ta }: BoardsWords) {
  try {
    receiveSummary(await boardsApi.patch(id, patch));
  } catch (error) {
    failed(t("toasts.updateFailed"), error, ta);
  }
}

/** true, когда доски больше нет. */
export async function deleteBoard(board: BoardSummary, { t, ta }: BoardsWords): Promise<boolean> {
  try {
    await boardsApi.remove(board.id);
    boardsResource.update((data) => ({ ...data, items: data.items.filter((b) => b.id !== board.id) }));
    toast.success(t(board.jira ? "toasts.stoppedSyncing" : "toasts.deleted", { board: board.name }));
    return true;
  } catch (error) {
    failed(t("toasts.deleteFailed"), error, ta);
    return false;
  }
}

/** Забрать последнее из Jira сейчас; доска перечитывается, когда синхронизация закончится. */
export async function syncBoard(id: string, { t, ta }: BoardsWords) {
  try {
    receiveSummary(await boardsApi.sync(id));
    await boardResource(id).refresh();
  } catch (error) {
    failed(t("toasts.syncFailed"), error, ta);
  }
}

/**
 * Доска для задач, которые приходят к человеку (TK-D4), или никакой (null). Прежняя доска их больше не получает,
 * новая получает каждую в колонку её вида.
 */
export async function chooseIncomingBoard(boardId: string | null, boardName: string, { t, ta }: BoardsWords) {
  try {
    const response = await boardsApi.setIncoming({ board_id: boardId });
    boardsResource.update(() => response);
    for (const board of response.items) void boardResource(board.id).refresh();
    toast.success(boardId ? t("toasts.workspaceTasksOn", { board: boardName }) : t("toasts.workspaceTasksOff"), {
      description: boardId ? t("toasts.workspaceTasksHint") : undefined,
    });
  } catch (error) {
    failed(t("toasts.workspaceTasksFailed"), error, ta);
  }
}
