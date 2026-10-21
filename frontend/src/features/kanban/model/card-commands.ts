import { toast } from "sonner";

import { copyText } from "@/lib/copy-text";

import { boardsApi } from "../api/boards-api";
import { tasksApi } from "../api/tasks-api";
import { insertCard, locate, moveToEdge } from "../domain/board-rules";
import { type Card, type JiraIssueRef, type Priority, TITLE_MAX } from "../domain/tasks-contract";
import type { BoardSnapshot } from "./board-store";
import { boardResource } from "./boards-resource";
import {
  boardIdOf,
  type CommandContext,
  countChange,
  dropCards,
  receiveCard,
  restoreCards,
  save,
} from "./command-context";
import { withUndo } from "./undo";

/*
 * Что делают с карточкой меню, кнопки и перетаскивание: изменение сразу видно и сохраняется; сбой возвращает
 * доску как было. Удаление ждёт, пока закроется тост с Undo.
 */

/** Карточка встала в колонку другого вида — её статус следует за видом колонки. */
const withKindOf = (s: BoardSnapshot, card: Card, columnId: string): Card => {
  const kind = s.columns[columnId]?.kind;
  return kind && kind !== card.status ? { ...card, status: kind } : card;
};

export function createCardCommands(ctx: CommandContext) {
  const id = () => boardIdOf(ctx);
  const words = () => ctx.words();

  /** Ответ сервера о перемещении; закрытая повторяющаяся задача приносит следующую — доска перечитывается. */
  function moved(before: Card | undefined, card: Card | null) {
    if (!card) return;
    receiveCard(ctx, card);
    if (before?.recurring && card.status === "done" && before.status !== "done") void boardResource(id()).refresh();
  }

  function sendMove(taskId: string, before: BoardSnapshot): Promise<void> {
    const at = locate(ctx.store.get().cardIds, taskId);
    if (!at) return Promise.resolve();
    const card = before.cards[taskId];
    ctx.store.update((s) => (card ? { ...s, cards: { ...s.cards, [taskId]: withKindOf(s, card, at.columnId) } } : s));
    return save(ctx, words().t("errors.saveChange"), before, () =>
      boardsApi.patchCard(id(), taskId, { column_id: at.columnId, position: at.index }),
    ).then((answer) => moved(card, answer));
  }

  return {
    setPriority(taskId: string, priority: Priority | null) {
      const before = ctx.store.get();
      const card = before.cards[taskId];
      if (!card) return;
      receiveCard(ctx, { ...card, priority, leo_fields: card.leo_fields.filter((f) => f !== "priority") });
      void save(ctx, words().t("errors.saveChange"), before, () =>
        boardsApi.patchCard(id(), taskId, { priority }),
      ).then((answer) => (answer ? receiveCard(ctx, answer) : undefined));
    },
    moveToEdge(taskId: string, columnId: string, edge: "top" | "bottom") {
      const before = ctx.store.get();
      ctx.store.update((s) => ({ ...s, cardIds: moveToEdge(s.cardIds, taskId, columnId, edge) }));
      return sendMove(taskId, before);
    },
    /** После перетаскивания: сохранить, куда легла карточка, если она сдвинулась. */
    commitDrop(taskId: string, before: BoardSnapshot) {
      const from = locate(before.cardIds, taskId);
      const to = locate(ctx.store.get().cardIds, taskId);
      if (!to || (from && from.columnId === to.columnId && from.index === to.index)) return;
      void sendMove(taskId, before);
    },
    renameCard(taskId: string) {
      const card = ctx.store.get().cards[taskId];
      if (!card) return;
      const { t, tc } = words();
      ctx.askName({
        title: t("commands.renameTask"),
        initial: card.title,
        submitLabel: tc("actions.rename"),
        onSubmit: (title) => {
          const before = ctx.store.get();
          receiveCard(ctx, { ...card, title });
          void save(ctx, t("errors.saveChange"), before, () => boardsApi.patchCard(id(), taskId, { title }));
        },
      });
    },
    addCard(columnId: string) {
      const { t } = words();
      ctx.askName({
        title: t("commands.newTaskIn", { column: ctx.store.get().columns[columnId]?.title ?? "" }),
        initial: "",
        submitLabel: t("addTask"),
        onSubmit: (title) =>
          void save(ctx, t("errors.addTask"), ctx.store.get(), () =>
            boardsApi.createCard(id(), { title, column_id: columnId, position: 0 }),
          ).then((card) => {
            if (!card) return;
            ctx.store.update((s) => ({
              ...s,
              cards: { ...s.cards, [card.id]: card },
              cardIds: insertCard(s.cardIds, columnId, 0, card.id),
            }));
            countChange(ctx, 1);
          }),
      });
    },
    /** Копия встаёт под оригиналом; отвечает её id (null, если не вышло). */
    duplicateCard(taskId: string): Promise<string | null> {
      const s = ctx.store.get();
      const at = locate(s.cardIds, taskId);
      const card = s.cards[taskId];
      if (!at || !card) return Promise.resolve(null);
      const { t } = words();
      const named = t("commands.copyTitle", { title: card.title });
      const title = named.length > TITLE_MAX ? card.title : named;
      const request = { title, column_id: at.columnId, position: at.index + 1, copy_of: taskId };
      return save(ctx, t("errors.addTask"), s, () => boardsApi.createCard(id(), request)).then((copy) => {
        if (!copy) return null;
        ctx.store.update((n) => ({
          ...n,
          cards: { ...n.cards, [copy.id]: copy },
          cardIds: insertCard(n.cardIds, at.columnId, at.index + 1, copy.id),
        }));
        countChange(ctx, 1);
        return copy.id;
      });
    },
    deleteCards(taskIds: string[], message: string) {
      const before = ctx.store.get();
      const { t, tc } = words();
      withUndo({
        message,
        undoLabel: tc("actions.undo"),
        hide: () => dropCards(ctx, taskIds),
        restore: () => restoreCards(ctx, before, taskIds),
        commit: () =>
          save(ctx, t("errors.deleteTasks", { count: taskIds.length }), before, () =>
            tasksApi.removeMany({ task_ids: taskIds }).then(() => true),
          ).then((done) => (done ? countChange(ctx, -taskIds.length) : undefined)),
      });
    },
    /** Ссылка на задачу: на этой доске с открытой панелью, у задачи Jira — на Jira; задача может быть и не на доске. */
    copyLink(taskId: string, jira: JiraIssueRef | null = ctx.store.get().cards[taskId]?.jira ?? null) {
      const { t, tc } = words();
      const params = new URLSearchParams({ board: id(), task: taskId });
      const url = jira?.url ?? `${window.location.origin}/app/kanban?${params}`;
      copyText(url).then(
        () => toast.success(jira ? t("commands.jiraLinkCopied", { key: jira.key }) : tc("feedback.linkCopied")),
        () => toast.error(tc("feedback.linkCopyFailed")),
      );
    },
  };
}

export type CardCommands = ReturnType<typeof createCardCommands>;
