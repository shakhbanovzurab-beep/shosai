import type { CardIds } from "../domain/board-rules";
import type { BoardDetail, BoardSummary, ColumnHead } from "../domain/boards-contract";
import type { BoardSticker } from "../domain/stickers-contract";
import type { Card } from "../domain/tasks-contract";

/*
 * Доска, какой её видит человек, как внешнее хранилище: колонки и карточки по id, порядок отдельно. Компонент
 * подписывается на свою часть (колонку, карточку), поэтому перемещение перерисовывает две колонки, правка —
 * одну карточку, а не всю доску. Новая версия с сервера принимается, когда своих изменений в пути нет.
 */

export type BoardSnapshot = {
  summary: BoardSummary;
  stickers: BoardSticker[];
  columnOrder: string[];
  columns: Record<string, ColumnHead>;
  cardIds: CardIds;
  cards: Record<string, Card>;
  revision: number;
};

export function snapshotOf(detail: BoardDetail): BoardSnapshot {
  const columns: Record<string, ColumnHead> = {};
  const cardIds: CardIds = {};
  const cards: Record<string, Card> = {};
  for (const { cards: list, ...head } of detail.columns) {
    columns[head.id] = head;
    cardIds[head.id] = list.map((card) => card.id);
    for (const card of list) cards[card.id] = card;
  }
  return {
    summary: detail.board,
    stickers: detail.stickers,
    columnOrder: detail.columns.map((c) => c.id),
    columns,
    cardIds,
    cards,
    revision: detail.revision,
  };
}

export type BoardStore = {
  get: () => BoardSnapshot;
  subscribe: (listener: () => void) => () => void;
  update: (change: (snapshot: BoardSnapshot) => BoardSnapshot) => void;
  /** Изменение уходит на сервер: пока оно в пути, серверная версия доски ждёт. */
  track: <T>(work: Promise<T>) => Promise<T>;
  /** Версия с сервера: новее нашей — принимается сразу или после изменений в пути. */
  receive: (detail: BoardDetail) => void;
};

export function createBoardStore(detail: BoardDetail): BoardStore {
  let snapshot = snapshotOf(detail);
  let inFlight = 0;
  let waiting: BoardDetail | null = null;
  const listeners = new Set<() => void>();

  const set = (next: BoardSnapshot) => {
    if (next === snapshot) return;
    snapshot = next;
    for (const listener of listeners) listener();
  };
  const accept = (incoming: BoardDetail) => {
    if (incoming.revision > snapshot.revision) set(snapshotOf(incoming));
  };

  return {
    get: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    update: (change) => set(change(snapshot)),
    async track(work) {
      inFlight++;
      try {
        return await work;
      } finally {
        inFlight--;
        if (inFlight === 0 && waiting) {
          const next = waiting;
          waiting = null;
          accept(next);
        }
      }
    },
    receive(incoming) {
      if (inFlight > 0) waiting = incoming;
      else accept(incoming);
    },
  };
}
