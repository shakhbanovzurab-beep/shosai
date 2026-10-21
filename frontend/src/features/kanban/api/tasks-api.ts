import { apiRequest, jsonBody } from "@/lib/api/request";

import type { StickerValue } from "../domain/stickers-contract";
import type {
  Attachment,
  AttachmentCreate,
  Comment,
  CommentCreate,
  CommentPatch,
  CommentsPage,
  DownloadLink,
  Subtask,
  SubtaskCreate,
  SubtaskPatch,
  TaskDetail,
  TaskPatch,
  TasksDelete,
} from "../domain/tasks-contract";

/* Задачи на `/v1/tasks*` (план tasks §3.3, TK-D12): поля, значения, подзадачи, комментарии и вложения. */

const path = (id: string, rest = "") => `/v1/tasks/${encodeURIComponent(id)}${rest}`;

export const tasksApi = {
  get: (id: string) => apiRequest<TaskDetail>(path(id)),
  patch: (id: string, body: TaskPatch) => apiRequest<TaskDetail>(path(id), jsonBody("PATCH", body)),
  removeMany: (body: TasksDelete) => apiRequest<void>("/v1/tasks/delete", jsonBody("POST", body)),
  putValue: (id: string, stickerId: string, value: StickerValue) =>
    apiRequest<StickerValue>(path(id, `/values/${encodeURIComponent(stickerId)}`), jsonBody("PUT", value)),
  clearValue: (id: string, stickerId: string) =>
    apiRequest<void>(path(id, `/values/${encodeURIComponent(stickerId)}`), { method: "DELETE" }),
  addSubtask: (id: string, body: SubtaskCreate) => apiRequest<Subtask>(path(id, "/subtasks"), jsonBody("POST", body)),
  patchSubtask: (id: string, subtaskId: string, body: SubtaskPatch) =>
    apiRequest<Subtask>(path(id, `/subtasks/${encodeURIComponent(subtaskId)}`), jsonBody("PATCH", body)),
  removeSubtask: (id: string, subtaskId: string) =>
    apiRequest<void>(path(id, `/subtasks/${encodeURIComponent(subtaskId)}`), { method: "DELETE" }),
  comments: (id: string, limit: number, cursor: string | null) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    return apiRequest<CommentsPage>(path(id, `/comments?${query}`));
  },
  /** Повтор с тем же ключом отвечает тем же комментарием, поэтому повторная отправка не дублирует его. */
  addComment: (id: string, body: CommentCreate, idempotencyKey: string) => {
    const request = jsonBody("POST", body);
    const headers = new Headers(request.headers);
    headers.set("Idempotency-Key", idempotencyKey);
    return apiRequest<Comment>(path(id, "/comments"), { ...request, headers });
  },
  editComment: (id: string, commentId: string, body: CommentPatch) =>
    apiRequest<Comment>(path(id, `/comments/${encodeURIComponent(commentId)}`), jsonBody("PATCH", body)),
  removeComment: (id: string, commentId: string) =>
    apiRequest<void>(path(id, `/comments/${encodeURIComponent(commentId)}`), { method: "DELETE" }),
  addAttachment: (id: string, body: AttachmentCreate) =>
    apiRequest<Attachment>(path(id, "/attachments"), jsonBody("POST", body)),
  downloadAttachment: (id: string, attachmentId: string) =>
    apiRequest<DownloadLink>(path(id, `/attachments/${encodeURIComponent(attachmentId)}/download`)),
  removeAttachment: (id: string, attachmentId: string) =>
    apiRequest<void>(path(id, `/attachments/${encodeURIComponent(attachmentId)}`), { method: "DELETE" }),
};
