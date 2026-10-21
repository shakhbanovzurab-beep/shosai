import { apiRequest, jsonBody } from "@/lib/api/request";

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

/*
 * Доски, колонки и карточки на `/v1/boards*` (план tasks §3.3, TK-D12). Пока у `tasks` нет API, им отвечают моки
 * слайса; шаг 9 плана tasks переводит этот шлюз на сгенерированный клиент.
 */

const path = (id: string, rest = "") => `/v1/boards/${encodeURIComponent(id)}${rest}`;
const part = (id: string) => encodeURIComponent(id);

export const boardsApi = {
  list: () => apiRequest<BoardsResponse>("/v1/boards"),
  create: (body: BoardCreate) => apiRequest<BoardSummary>("/v1/boards", jsonBody("POST", body)),
  setIncoming: (body: IncomingTarget) => apiRequest<BoardsResponse>("/v1/boards/incoming", jsonBody("PUT", body)),
  get: (id: string) => apiRequest<BoardDetail>(path(id)),
  patch: (id: string, body: BoardPatch) => apiRequest<BoardSummary>(path(id), jsonBody("PATCH", body)),
  remove: (id: string) => apiRequest<void>(path(id), { method: "DELETE" }),
  saveLayout: (id: string, body: Layout) => apiRequest<void>(path(id, "/layout"), jsonBody("PUT", body)),
  sync: (id: string) => apiRequest<BoardSummary>(path(id, "/sync"), { method: "POST" }),
  createColumn: (id: string, body: ColumnCreate) =>
    apiRequest<ColumnHead>(path(id, "/columns"), jsonBody("POST", body)),
  patchColumn: (id: string, columnId: string, body: ColumnPatch) =>
    apiRequest<ColumnHead>(path(id, `/columns/${part(columnId)}`), jsonBody("PATCH", body)),
  removeColumn: (id: string, columnId: string) =>
    apiRequest<void>(path(id, `/columns/${part(columnId)}`), { method: "DELETE" }),
  createCard: (id: string, body: CardCreate) => apiRequest<Card>(path(id, "/cards"), jsonBody("POST", body)),
  patchCard: (id: string, taskId: string, body: CardPatch) =>
    apiRequest<Card>(path(id, `/cards/${part(taskId)}`), jsonBody("PATCH", body)),
  jiraAvailable: () => apiRequest<JiraAvailable>("/v1/boards/jira/available"),
  connectJira: (body: JiraConnect) => apiRequest<BoardSummary>("/v1/boards/jira", jsonBody("POST", body)),
};
