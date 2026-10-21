"use client";

import { toast } from "sonner";

import { saveFile } from "@/lib/save-file";

import { tasksApi } from "../api/tasks-api";
import type { Attachment, Cover, TaskDetail } from "../domain/tasks-contract";
import type { BoardStore } from "./board-store";
import { changeTask, freshTask, reportFailure, showTask, type TaskWords } from "./task-sync";
import { withUndo } from "./undo";
import { describeProblem } from "./words";

/*
 * Готовые вложения из панели: обложка карточки из картинки, скачивание по свежей ссылке, удаление с Undo. Число
 * вложений и обложка на карточке идут за панелью сразу.
 */

const coverOf = (attachment: Attachment): Cover => ({
  attachment_id: attachment.id,
  preview_url: attachment.preview_url,
});

export function attachmentActions(taskId: string, store: BoardStore | null, words: TaskWords) {
  return {
    /** Сделать картинку обложкой или убрать обложку (null). */
    setCover(attachment: Attachment | null) {
      let before: Cover | null = null;
      return changeTask(taskId, store, words, {
        apply: (detail) => {
          before = detail.cover;
          return { ...detail, cover: attachment ? coverOf(attachment) : null };
        },
        revert: (detail) => ({ ...detail, cover: before }),
        work: async () => freshTask(await tasksApi.patch(taskId, { cover_attachment_id: attachment?.id ?? null })),
      });
    },
    async download(attachment: Attachment, failed: string) {
      try {
        const { url } = await tasksApi.downloadAttachment(taskId, attachment.id);
        saveFile(url, attachment.name);
      } catch (error) {
        toast.error(failed, { description: describeProblem(error, words.ta) });
      }
    },
    remove(attachment: Attachment, message: string) {
      let index = 0;
      let wasCover = false;
      const hide = () =>
        showTask(taskId, store, (detail): TaskDetail => {
          const at = detail.attachments.findIndex((item) => item.id === attachment.id);
          if (at < 0) return detail;
          index = at;
          wasCover = detail.cover?.attachment_id === attachment.id;
          return {
            ...detail,
            attachments: detail.attachments.filter((item) => item.id !== attachment.id),
            cover: wasCover ? null : detail.cover,
          };
        });
      const restore = () =>
        showTask(taskId, store, (detail) =>
          detail.attachments.some((item) => item.id === attachment.id)
            ? detail
            : {
                ...detail,
                attachments: detail.attachments.toSpliced(index, 0, attachment),
                cover: wasCover ? coverOf(attachment) : detail.cover,
              },
        );
      withUndo({
        message,
        undoLabel: words.tc("actions.undo"),
        hide,
        restore,
        commit: () =>
          tasksApi.removeAttachment(taskId, attachment.id).then(
            () => undefined,
            (error: unknown) => {
              restore();
              reportFailure(error, words);
            },
          ),
      });
    },
  };
}
