"use client";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";

import { kanbanApi } from "../api/kanban-api";
import type { BoardSummary } from "../domain/board";
import type { BoardPatch, ConnectJiraBoardRequest, CreateBoardRequest } from "../domain/contract";
import { boardResource, boardsResource, receiveSummary } from "./boards-resource";
import type { BoardWords } from "./words";

const failed = (title: string, error: unknown) => {
  toast.error(title, { description: apiErrorDescription(error) });
  return null;
};

/** Creates an app board; resolves to it, or null after reporting the failure. */
export async function createBoard(request: CreateBoardRequest, t: BoardWords): Promise<BoardSummary | null> {
  try {
    const board = await kanbanApi.createBoard(request);
    receiveSummary(board);
    return board;
  } catch (error) {
    return failed(t("toasts.createFailed"), error);
  }
}

/** Starts a two-way sync with a Jira board; resolves to the new board, which syncs in the background. */
export async function connectJiraBoard(request: ConnectJiraBoardRequest, t: BoardWords): Promise<BoardSummary | null> {
  try {
    const board = await kanbanApi.connectJiraBoard(request);
    receiveSummary(board);
    return board;
  } catch (error) {
    return failed(t("toasts.connectFailed"), error);
  }
}

export async function updateBoard(id: string, patch: BoardPatch, t: BoardWords) {
  try {
    receiveSummary(await kanbanApi.patchBoard(id, patch));
  } catch (error) {
    failed(t("toasts.updateFailed"), error);
  }
}

/** Resolves to true once the board is gone. */
export async function deleteBoard(board: BoardSummary, t: BoardWords): Promise<boolean> {
  try {
    await kanbanApi.deleteBoard(board.id);
    boardsResource.update((data) => ({ ...data, boards: data.boards.filter((b) => b.id !== board.id) }));
    toast.success(t(board.jira ? "toasts.stoppedSyncing" : "toasts.deleted", { board: board.name }));
    return true;
  } catch (error) {
    failed(t("toasts.deleteFailed"), error);
    return false;
  }
}

/** Pulls the latest from Jira now; the board re-reads itself when the sync finishes. */
export async function syncBoard(id: string, t: BoardWords) {
  try {
    receiveSummary(await kanbanApi.syncBoard(id));
    await boardResource(id).refresh();
  } catch (error) {
    failed(t("toasts.syncFailed"), error);
  }
}

/**
 * Shows the user's workspace tasks on this board, or nowhere (null). The old board loses those cards
 * and the new one gets them, each in the column matching the task's status.
 */
export async function chooseWorkspaceTasksBoard(boardId: string | null, boardName: string, t: BoardWords) {
  try {
    const response = await kanbanApi.setWorkspaceTasksBoard({ board_id: boardId });
    boardsResource.update(() => response);
    for (const board of response.boards) void boardResource(board.id).refresh();
    toast.success(boardId ? t("toasts.workspaceTasksOn", { board: boardName }) : t("toasts.workspaceTasksOff"), {
      description: boardId ? t("toasts.workspaceTasksHint") : undefined,
    });
  } catch (error) {
    failed(t("toasts.workspaceTasksFailed"), error);
  }
}
