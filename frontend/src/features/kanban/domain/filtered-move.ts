import type { CardIds } from "./board-rules";

/* Перетаскивание под фильтром: человек видит только часть карточек колонки (план пакета §4.5). */

/** Видимые карточки каждой колонки в их порядке. */
export function visibleIds(cardIds: CardIds, shown: ReadonlySet<string>): CardIds {
  return Object.fromEntries(
    Object.entries(cardIds).map(([column, ids]) => [column, ids.filter((id) => shown.has(id))]),
  );
}

/**
 * Полный порядок после переноса среди видимых: карточка встаёт сразу после видимой карточки над ней, а если над
 * ней никого не видно — в начало колонки. Скрытые карточки остаются на своих местах.
 */
export function placeAmongVisible(full: CardIds, visibleAfter: CardIds, movedId: string): CardIds {
  const column = Object.keys(visibleAfter).find((id) => visibleAfter[id]?.includes(movedId));
  if (column === undefined) return full;
  const visible = visibleAfter[column] ?? [];
  const above = visible[visible.indexOf(movedId) - 1];
  const without = Object.fromEntries(
    Object.entries(full).map(([id, ids]) => [id, ids.filter((card) => card !== movedId)]),
  );
  const ids = without[column] ?? [];
  const at = above === undefined ? 0 : ids.indexOf(above) + 1;
  return { ...without, [column]: [...ids.slice(0, at), movedId, ...ids.slice(at)] };
}
