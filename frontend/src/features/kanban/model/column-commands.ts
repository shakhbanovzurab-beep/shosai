import { boardsApi } from "../api/boards-api";
import { shiftColumn, sortByPriority } from "../domain/board-rules";
import type { ColumnHead } from "../domain/boards-contract";
import type { BoardSnapshot } from "./board-store";
import type { CardCommands } from "./card-commands";
import { boardIdOf, type CommandContext, save } from "./command-context";

/* Что делают с колонкой меню и перетаскивание: имя, место, сортировка, очистка с Undo. */

/** Раскладка доски целиком: колонки с названиями и порядок их карточек. */
const layoutOf = (s: BoardSnapshot) => ({
  columns: s.columnOrder.map((id) => ({ id, title: s.columns[id]?.title ?? id, task_ids: s.cardIds[id] ?? [] })),
});

export function createColumnCommands(ctx: CommandContext, cards: CardCommands) {
  const id = () => boardIdOf(ctx);
  const failure = () => ctx.words().t("errors.saveBoard");

  function patchHead(columnId: string, change: Partial<ColumnHead>) {
    ctx.store.update((s) => {
      const head = s.columns[columnId];
      return head ? { ...s, columns: { ...s.columns, [columnId]: { ...head, ...change } } } : s;
    });
  }

  /** Колонка встала на новое место: на сервер уходит её позиция. */
  function sendPosition(columnId: string, before: BoardSnapshot) {
    const position = ctx.store.get().columnOrder.indexOf(columnId);
    if (position < 0 || position === before.columnOrder.indexOf(columnId)) return;
    void save(ctx, failure(), before, () => boardsApi.patchColumn(id(), columnId, { position }));
  }

  return {
    renameColumn(columnId: string) {
      const { t, tc } = ctx.words();
      ctx.askName({
        title: t("commands.renameColumn"),
        initial: ctx.store.get().columns[columnId]?.title ?? "",
        submitLabel: tc("actions.rename"),
        onSubmit: (title) => {
          const before = ctx.store.get();
          patchHead(columnId, { title });
          void save(ctx, failure(), before, () => boardsApi.patchColumn(id(), columnId, { title }));
        },
      });
    },
    /** На одно место к началу (-1) или к концу (1) доски — в какую бы сторону ни читался язык. */
    shiftColumn(columnId: string, by: -1 | 1) {
      const before = ctx.store.get();
      ctx.store.update((s) => ({ ...s, columnOrder: shiftColumn(s.columnOrder, columnId, by) }));
      sendPosition(columnId, before);
    },
    /** После перетаскивания колонки. */
    commitColumnMove(columnId: string, before: BoardSnapshot) {
      sendPosition(columnId, before);
    },
    sortColumn(columnId: string) {
      const before = ctx.store.get();
      ctx.store.update((s) => ({
        ...s,
        cardIds: { ...s.cardIds, [columnId]: sortByPriority(s.cardIds[columnId] ?? [], s.cards) },
      }));
      void save(ctx, failure(), before, () => boardsApi.saveLayout(id(), layoutOf(ctx.store.get())));
    },
    /** Задачи пространств и Jira остаются: они уходят, когда их закрывают или переназначают там. */
    clearColumn(columnId: string) {
      const s = ctx.store.get();
      const ids = (s.cardIds[columnId] ?? []).filter((taskId) => s.cards[taskId]?.can_delete);
      if (ids.length === 0) return;
      const message = ctx
        .words()
        .t("commands.cleared", { count: ids.length, column: s.columns[columnId]?.title ?? "" });
      cards.deleteCards(ids, message);
    },
  };
}

export type ColumnCommands = ReturnType<typeof createColumnCommands>;
