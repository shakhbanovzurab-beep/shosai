import { boardsApi } from "../api/boards-api";
import { heirOf } from "../domain/board-rules";
import type { ColumnCreate, ColumnHead } from "../domain/boards-contract";
import type { Color } from "../domain/stickers-contract";
import { boardIdOf, type CommandContext, save } from "./command-context";
import { withUndo } from "./undo";

/* Колонка появляется, меняет цвет, сворачивается и уходит, не теряя карточек (TK-D12, KG-D9). */

export function createColumnLifecycle(ctx: CommandContext) {
  const id = () => boardIdOf(ctx);
  const failure = () => ctx.words().t("errors.saveBoard");

  function patchHead(columnId: string, change: Partial<ColumnHead>) {
    const before = ctx.store.get();
    const head = before.columns[columnId];
    if (!head) return;
    ctx.store.update((s) => ({ ...s, columns: { ...s.columns, [columnId]: { ...head, ...change } } }));
    void save(ctx, failure(), before, () => boardsApi.patchColumn(id(), columnId, change));
  }

  return {
    /** Новая колонка на `position`; отдаёт её или null, сообщив о сбое. */
    async addColumn(request: ColumnCreate): Promise<ColumnHead | null> {
      const created = await save(ctx, ctx.words().t("errors.addColumn"), ctx.store.get(), () =>
        boardsApi.createColumn(id(), request),
      );
      if (!created) return null;
      ctx.store.update((s) => {
        const order = [...s.columnOrder];
        order.splice(Math.min(request.position, order.length), 0, created.id);
        return {
          ...s,
          columnOrder: order,
          columns: { ...s.columns, [created.id]: created },
          cardIds: { ...s.cardIds, [created.id]: [] },
        };
      });
      return created;
    },
    setColour(columnId: string, color: Color | null) {
      patchHead(columnId, { color });
    },
    setCollapsed(columnId: string, collapsed: boolean) {
      patchHead(columnId, { collapsed });
    },
    /** Удалить с Undo: колонка исчезает, её карточки встают наверх наследника; запрос — когда закроется тост. */
    deleteColumn(columnId: string) {
      const before = ctx.store.get();
      const heir = heirOf(before.columnOrder, before.columns, columnId);
      const head = before.columns[columnId];
      if (!heir || !head) return;
      const { t, tc } = ctx.words();
      const moved = before.cardIds[columnId] ?? [];
      const movedIds = new Set(moved);
      withUndo({
        message: t("commands.columnDeleted", { column: head.title }),
        undoLabel: tc("actions.undo"),
        hide: () =>
          ctx.store.update((s) => {
            const { [columnId]: _gone, ...cardIds } = s.cardIds;
            return {
              ...s,
              columnOrder: s.columnOrder.filter((c) => c !== columnId),
              cardIds: { ...cardIds, [heir]: [...moved, ...(cardIds[heir] ?? [])] },
            };
          }),
        restore: () =>
          ctx.store.update((s) => ({
            ...s,
            columnOrder: before.columnOrder,
            cardIds: {
              ...s.cardIds,
              [columnId]: moved,
              [heir]: (s.cardIds[heir] ?? []).filter((taskId) => !movedIds.has(taskId)),
            },
          })),
        commit: () => save(ctx, failure(), before, () => boardsApi.removeColumn(id(), columnId)),
      });
    },
  };
}

export type ColumnLifecycle = ReturnType<typeof createColumnLifecycle>;
