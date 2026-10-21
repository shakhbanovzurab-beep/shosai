"use client";

import { tasksApi } from "../api/tasks-api";
import type { Comment } from "../domain/tasks-contract";
import type { BoardStore } from "./board-store";
import { changeComments } from "./comments-resource";
import { isLocalId, localId, reportFailure, showTask, type TaskWords } from "./task-sync";
import { withUndo } from "./undo";

/*
 * Комментарии из панели: свой виден сразу, число комментариев на карточке идёт за ним. Отказ убирает только
 * это изменение и говорит, почему; текст неотправленного возвращается в поле ввода.
 */

type Author = Comment["author"];

const replaced = (comment: Comment) => (items: Comment[]) =>
  items.map((item) => (item.id === comment.id ? comment : item));

export function commentActions(taskId: string, author: Author, store: BoardStore | null, words: TaskWords) {
  const count = (delta: number) =>
    showTask(taskId, store, (detail) => ({ ...detail, comment_count: Math.max(0, detail.comment_count + delta) }));

  return {
    /** Отправить; при отказе — false, и текст остаётся у человека. */
    async add(body: string) {
      const local: Comment = { id: localId(), author, body, created_at: new Date().toISOString(), edited_at: null };
      changeComments(taskId, (items) => [local, ...items]);
      count(1);
      try {
        const saved = await tasksApi.addComment(taskId, { body }, crypto.randomUUID());
        // Страница, загруженная за это время, могла уже принести его: строка остаётся одна.
        changeComments(taskId, (items) =>
          items.some((item) => item.id === saved.id)
            ? items.filter((item) => item.id !== local.id)
            : items.map((item) => (item.id === local.id ? saved : item)),
        );
        return true;
      } catch (error) {
        changeComments(taskId, (items) => items.filter((item) => item.id !== local.id));
        count(-1);
        reportFailure(error, words);
        return false;
      }
    },
    async edit(comment: Comment, body: string) {
      if (isLocalId(comment.id) || body === comment.body) return true;
      changeComments(taskId, replaced({ ...comment, body, edited_at: new Date().toISOString() }));
      try {
        changeComments(taskId, replaced(await tasksApi.editComment(taskId, comment.id, { body })));
        return true;
      } catch (error) {
        changeComments(taskId, replaced(comment));
        reportFailure(error, words);
        return false;
      }
    },
    remove(comment: Comment, message: string) {
      if (isLocalId(comment.id)) return;
      let index = 0;
      const restore = () => {
        changeComments(taskId, (items) =>
          items.some((item) => item.id === comment.id) ? items : items.toSpliced(index, 0, comment),
        );
        count(1);
      };
      withUndo({
        message,
        undoLabel: words.tc("actions.undo"),
        hide: () => {
          changeComments(taskId, (items) => {
            index = Math.max(
              0,
              items.findIndex((item) => item.id === comment.id),
            );
            return items.filter((item) => item.id !== comment.id);
          });
          count(-1);
        },
        restore,
        commit: () =>
          tasksApi.removeComment(taskId, comment.id).catch((error: unknown) => {
            restore();
            reportFailure(error, words);
          }),
      });
    },
  };
}
