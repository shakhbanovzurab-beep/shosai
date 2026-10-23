import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

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

const task = (id: string) => ({ params: { path: { task_id: id } } });
const value = (id: string, stickerId: string) => ({ params: { path: { task_id: id, sticker_id: stickerId } } });
const subtask = (id: string, subtaskId: string) => ({ params: { path: { task_id: id, subtask_id: subtaskId } } });
const comment = (id: string, commentId: string) => ({ params: { path: { task_id: id, comment_id: commentId } } });
const attachment = (id: string, attachmentId: string) => ({
  params: { path: { task_id: id, attachment_id: attachmentId } },
});

export const tasksApi = {
  get: (id: string): Promise<TaskDetail> => dataOf(apiClient.GET("/v1/tasks/{task_id}", task(id))),
  patch: (id: string, body: TaskPatch): Promise<TaskDetail> =>
    dataOf(apiClient.PATCH("/v1/tasks/{task_id}", { ...task(id), body })),
  removeMany: (body: TasksDelete): Promise<void> => dataOf(apiClient.POST("/v1/tasks/delete", { body })),
  putValue: (id: string, stickerId: string, body: StickerValue): Promise<StickerValue> =>
    dataOf(apiClient.PUT("/v1/tasks/{task_id}/values/{sticker_id}", { ...value(id, stickerId), body })),
  clearValue: (id: string, stickerId: string): Promise<void> =>
    dataOf(apiClient.DELETE("/v1/tasks/{task_id}/values/{sticker_id}", value(id, stickerId))),
  addSubtask: (id: string, body: SubtaskCreate): Promise<Subtask> =>
    dataOf(apiClient.POST("/v1/tasks/{task_id}/subtasks", { ...task(id), body })),
  patchSubtask: (id: string, subtaskId: string, body: SubtaskPatch): Promise<Subtask> =>
    dataOf(apiClient.PATCH("/v1/tasks/{task_id}/subtasks/{subtask_id}", { ...subtask(id, subtaskId), body })),
  removeSubtask: (id: string, subtaskId: string): Promise<void> =>
    dataOf(apiClient.DELETE("/v1/tasks/{task_id}/subtasks/{subtask_id}", subtask(id, subtaskId))),
  comments: (id: string, limit: number, cursor: string | null): Promise<CommentsPage> =>
    dataOf(
      apiClient.GET("/v1/tasks/{task_id}/comments", {
        params: { path: { task_id: id }, query: { limit, ...(cursor ? { cursor } : {}) } },
      }),
    ),
  /** Повтор с тем же ключом отвечает тем же комментарием, поэтому повторная отправка не дублирует его. */
  addComment: (id: string, body: CommentCreate, idempotencyKey: string): Promise<Comment> =>
    dataOf(
      apiClient.POST("/v1/tasks/{task_id}/comments", {
        params: { path: { task_id: id }, header: { "Idempotency-Key": idempotencyKey } },
        body,
      }),
    ),
  editComment: (id: string, commentId: string, body: CommentPatch): Promise<Comment> =>
    dataOf(apiClient.PATCH("/v1/tasks/{task_id}/comments/{comment_id}", { ...comment(id, commentId), body })),
  removeComment: (id: string, commentId: string): Promise<void> =>
    dataOf(apiClient.DELETE("/v1/tasks/{task_id}/comments/{comment_id}", comment(id, commentId))),
  addAttachment: (id: string, body: AttachmentCreate): Promise<Attachment> =>
    dataOf(apiClient.POST("/v1/tasks/{task_id}/attachments", { ...task(id), body })),
  downloadAttachment: (id: string, attachmentId: string): Promise<DownloadLink> =>
    dataOf(apiClient.GET("/v1/tasks/{task_id}/attachments/{attachment_id}/download", attachment(id, attachmentId))),
  removeAttachment: (id: string, attachmentId: string): Promise<void> =>
    dataOf(apiClient.DELETE("/v1/tasks/{task_id}/attachments/{attachment_id}", attachment(id, attachmentId))),
};
