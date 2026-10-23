import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type {
  BoardCreate,
  BoardDetail,
  BoardPatch,
  BoardSummary,
  BoardsResponse,
  CardCreate,
  CardPatch,
  ColumnCreate,
  ColumnHead,
  ColumnPatch,
  IncomingTarget,
  JiraAvailable,
  JiraConnect,
  Layout,
} from "../domain/boards-contract";
import type { Card } from "../domain/tasks-contract";

/* Доски, колонки и карточки на `/v1/boards*` (план tasks §3.3, TK-D12). */

const board = (id: string) => ({ params: { path: { board_id: id } } });
const column = (id: string, columnId: string) => ({ params: { path: { board_id: id, column_id: columnId } } });
const card = (id: string, taskId: string) => ({ params: { path: { board_id: id, task_id: taskId } } });

export const boardsApi = {
  list: (): Promise<BoardsResponse> => dataOf(apiClient.GET("/v1/boards")),
  create: (body: BoardCreate): Promise<BoardSummary> => dataOf(apiClient.POST("/v1/boards", { body })),
  setIncoming: (body: IncomingTarget): Promise<BoardsResponse> =>
    dataOf(apiClient.PUT("/v1/boards/incoming", { body })),
  get: (id: string): Promise<BoardDetail> => dataOf(apiClient.GET("/v1/boards/{board_id}", board(id))),
  patch: (id: string, body: BoardPatch): Promise<BoardSummary> =>
    dataOf(apiClient.PATCH("/v1/boards/{board_id}", { ...board(id), body })),
  remove: (id: string): Promise<void> => dataOf(apiClient.DELETE("/v1/boards/{board_id}", board(id))),
  saveLayout: (id: string, body: Layout): Promise<void> =>
    dataOf(apiClient.PUT("/v1/boards/{board_id}/layout", { ...board(id), body })),
  sync: (id: string): Promise<BoardSummary> => dataOf(apiClient.POST("/v1/boards/{board_id}/sync", board(id))),
  createColumn: (id: string, body: ColumnCreate): Promise<ColumnHead> =>
    dataOf(apiClient.POST("/v1/boards/{board_id}/columns", { ...board(id), body })),
  patchColumn: (id: string, columnId: string, body: ColumnPatch): Promise<ColumnHead> =>
    dataOf(apiClient.PATCH("/v1/boards/{board_id}/columns/{column_id}", { ...column(id, columnId), body })),
  removeColumn: (id: string, columnId: string): Promise<void> =>
    dataOf(apiClient.DELETE("/v1/boards/{board_id}/columns/{column_id}", column(id, columnId))),
  createCard: (id: string, body: CardCreate): Promise<Card> =>
    dataOf(apiClient.POST("/v1/boards/{board_id}/cards", { ...board(id), body })),
  patchCard: (id: string, taskId: string, body: CardPatch): Promise<Card> =>
    dataOf(apiClient.PATCH("/v1/boards/{board_id}/cards/{task_id}", { ...card(id, taskId), body })),
  jiraAvailable: (): Promise<JiraAvailable> => dataOf(apiClient.GET("/v1/boards/jira/available")),
  connectJira: (body: JiraConnect): Promise<BoardSummary> => dataOf(apiClient.POST("/v1/boards/jira", { body })),
};
