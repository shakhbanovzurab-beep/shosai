import { apiRequest, jsonBody } from "@/lib/api-client";

import type { BoardDetail, BoardSummary, Task } from "../domain/board";
import type {
  BoardPatch,
  BoardsResponse,
  ConnectJiraBoardRequest,
  CreateBoardRequest,
  JiraBoardsResponse,
  LayoutUpdate,
  TaskCreate,
  TaskPatch,
  WorkspaceTasksTarget,
} from "../domain/contract";

function request<T>(path: string, init?: RequestInit) {
  return apiRequest<T>(`/api/kanban${path}`, init);
}
const board = (id: string, rest = "") => `/boards/${encodeURIComponent(id)}${rest}`;

export const kanbanApi = {
  listBoards: () => request<BoardsResponse>("/boards"),
  createBoard: (body: CreateBoardRequest) => request<BoardSummary>("/boards", jsonBody("POST", body)),
  getBoard: (id: string) => request<BoardDetail>(board(id)),
  patchBoard: (id: string, body: BoardPatch) => request<BoardSummary>(board(id), jsonBody("PATCH", body)),
  deleteBoard: (id: string) => request<void>(board(id), { method: "DELETE" }),
  saveLayout: (id: string, body: LayoutUpdate) => request<void>(board(id, "/layout"), jsonBody("PUT", body)),
  syncBoard: (id: string) => request<BoardSummary>(board(id, "/sync"), { method: "POST" }),
  createTask: (id: string, body: TaskCreate) => request<Task>(board(id, "/tasks"), jsonBody("POST", body)),
  patchTask: (id: string, taskId: string, body: TaskPatch) =>
    request<Task>(board(id, `/tasks/${encodeURIComponent(taskId)}`), jsonBody("PATCH", body)),
  deleteTasks: (id: string, taskIds: string[]) =>
    request<void>(board(id, "/tasks/delete"), jsonBody("POST", { task_ids: taskIds })),
  setWorkspaceTasksBoard: (body: WorkspaceTasksTarget) =>
    request<BoardsResponse>("/workspace-tasks", jsonBody("PUT", body)),
  jiraBoards: () => request<JiraBoardsResponse>("/jira/boards"),
  connectJiraBoard: (body: ConnectJiraBoardRequest) => request<BoardSummary>("/jira/boards", jsonBody("POST", body)),
};
