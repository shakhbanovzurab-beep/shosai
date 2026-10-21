import { toast } from "sonner";

import { insertCard, locate } from "../domain/board-rules";
import type { Card } from "../domain/tasks-contract";
import type { BoardSnapshot, BoardStore } from "./board-store";
import { adjustTaskCount } from "./boards-resource";
import { type ApiWords, type CommonWords, describeProblem, type KanbanWords } from "./words";

/*
 * Что нужно командам доски: её хранилище, слова на языке человека (читаются в момент вызова, чтобы смена
 * языка не оставляла старых) и диалог имени, который показывает интерфейс.
 */

export type NameAsk = { title: string; initial: string; submitLabel: string; onSubmit: (name: string) => void };
export type CommandWords = { t: KanbanWords; tc: CommonWords; ta: ApiWords };

export type CommandContext = {
  store: BoardStore;
  words: () => CommandWords;
  askName: (ask: NameAsk) => void;
};

export const boardIdOf = (ctx: CommandContext) => ctx.store.get().summary.id;

/**
 * Изменение, которое доска уже показала: отправить; при сбое — тост с причиной и откат к `before`.
 * Возвращает ответ сервера или null.
 */
export async function save<T>(
  ctx: CommandContext,
  failure: string,
  before: BoardSnapshot,
  work: () => Promise<T>,
): Promise<T | null> {
  try {
    return await ctx.store.track(work());
  } catch (error) {
    toast.error(failure, { description: describeProblem(error, ctx.words().ta) });
    ctx.store.update(() => before);
    return null;
  }
}

/** Карточка, как её вернул сервер, — в хранилище доски. */
export function receiveCard(ctx: CommandContext, card: Card) {
  ctx.store.update((s) => ({ ...s, cards: { ...s.cards, [card.id]: card } }));
}

/** Карточки уходят с доски: из порядка и из счётчика доски в списке. */
export function dropCards(ctx: CommandContext, ids: string[]) {
  const gone = new Set(ids);
  ctx.store.update((s) => ({
    ...s,
    cardIds: Object.fromEntries(Object.entries(s.cardIds).map(([c, list]) => [c, list.filter((id) => !gone.has(id))])),
  }));
}

/** Undo удаления: карточки возвращаются на прежние места, остальные изменения доски остаются. */
export function restoreCards(ctx: CommandContext, before: BoardSnapshot, ids: string[]) {
  ctx.store.update((s) => {
    let cardIds = s.cardIds;
    const cards = { ...s.cards };
    for (const id of ids) {
      const at = locate(before.cardIds, id);
      const card = before.cards[id];
      if (!at || !card || locate(cardIds, id)) continue;
      cardIds = insertCard(cardIds, at.columnId, at.index, id);
      cards[id] = card;
    }
    return { ...s, cardIds, cards };
  });
}

export function countChange(ctx: CommandContext, by: number) {
  adjustTaskCount(boardIdOf(ctx), by);
}
