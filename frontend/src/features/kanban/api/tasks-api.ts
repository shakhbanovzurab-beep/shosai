import { apiRequest, jsonBody } from "@/lib/api/request";

import type { StickerValue } from "../domain/stickers-contract";
import type { TaskDetail, TaskPatch, TasksDelete } from "../domain/tasks-contract";

/* Задачи на `/v1/tasks*` (план tasks §3.3, TK-D12); подзадачи, комментарии и вложения добавляют шаги панели. */

const path = (id: string, rest = "") => `/v1/tasks/${encodeURIComponent(id)}${rest}`;

export const tasksApi = {
  get: (id: string) => apiRequest<TaskDetail>(path(id)),
  patch: (id: string, body: TaskPatch) => apiRequest<TaskDetail>(path(id), jsonBody("PATCH", body)),
  removeMany: (body: TasksDelete) => apiRequest<void>("/v1/tasks/delete", jsonBody("POST", body)),
  putValue: (id: string, stickerId: string, value: StickerValue) =>
    apiRequest<StickerValue>(path(id, `/values/${encodeURIComponent(stickerId)}`), jsonBody("PUT", value)),
  clearValue: (id: string, stickerId: string) =>
    apiRequest<void>(path(id, `/values/${encodeURIComponent(stickerId)}`), { method: "DELETE" }),
};
