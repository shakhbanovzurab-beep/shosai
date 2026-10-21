import type { Card, Priority } from "./tasks-contract";

/*
 * Порядок карточек на доске: id карточек по колонкам. Чистые функции — их зовут действия модели до ответа
 * сервера и перетаскивание.
 */

export type CardIds = Record<string, string[]>;
export type CardLocation = { columnId: string; index: number };

export function locate(cardIds: CardIds, taskId: string): CardLocation | null {
  for (const [columnId, ids] of Object.entries(cardIds)) {
    const index = ids.indexOf(taskId);
    if (index >= 0) return { columnId, index };
  }
  return null;
}

export function withoutCard(cardIds: CardIds, taskId: string): CardIds {
  const at = locate(cardIds, taskId);
  if (!at) return cardIds;
  return { ...cardIds, [at.columnId]: cardIds[at.columnId].filter((id) => id !== taskId) };
}

export function insertCard(cardIds: CardIds, columnId: string, index: number, taskId: string): CardIds {
  const ids = cardIds[columnId] ?? [];
  const at = Math.max(0, Math.min(index, ids.length));
  return { ...cardIds, [columnId]: [...ids.slice(0, at), taskId, ...ids.slice(at)] };
}

/** Переставить карточку на `index` в колонке — ту же или другую. */
export const placeCard = (cardIds: CardIds, taskId: string, columnId: string, index: number) =>
  insertCard(withoutCard(cardIds, taskId), columnId, index, taskId);

/** Наверх или вниз колонки. */
export function moveToEdge(cardIds: CardIds, taskId: string, columnId: string, edge: "top" | "bottom") {
  const rest = withoutCard(cardIds, taskId);
  return insertCard(rest, columnId, edge === "top" ? 0 : (rest[columnId] ?? []).length, taskId);
}

const PRIORITY_RANK: Record<Priority, number> = { high: 0, medium: 1, low: 2 };
const rankOf = (priority: Priority | null) => (priority === null ? 3 : PRIORITY_RANK[priority]);

/** По приоритету, задачи без приоритета — последними; равные сохраняют порядок. */
export const sortByPriority = (ids: string[], cards: Record<string, Card>) =>
  ids.toSorted((a, b) => rankOf(cards[a]?.priority ?? null) - rankOf(cards[b]?.priority ?? null));

/**
 * Меняет колонку местами с предыдущей (-1) или следующей (1) в порядке доски, который читается от начала строки:
 * слева направо или справа налево в арабском. На краях порядок не меняется.
 */
export function shiftColumn(order: string[], columnId: string, by: -1 | 1): string[] {
  const from = order.indexOf(columnId);
  const to = from + by;
  if (from < 0 || to < 0 || to >= order.length) return order;
  const next = [...order];
  [next[from], next[to]] = [next[to], next[from]];
  return next;
}
