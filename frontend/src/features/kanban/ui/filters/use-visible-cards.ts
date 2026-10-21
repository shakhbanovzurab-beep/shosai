"use client";

import type { CardIds } from "../../domain/board-rules";
import type { BoardFilter } from "../../domain/filter-contract";
import { cardMatches, forVisible, isFiltering } from "../../domain/filter-rules";
import { visibleIds } from "../../domain/filtered-move";
import type { Card } from "../../domain/tasks-contract";
import { useBoardSelector, useToday } from "../../model/board-hooks";
import type { BoardSnapshot } from "../../model/board-store";
import { useFilterAddress } from "./filter-address";

/*
 * Что показывает доска под фильтром. Совпадения считаются один раз на версию карточек и фильтра, списки колонок —
 * один раз на их версию: подписчики получают те же массивы, пока ничего не изменилось.
 */

const NONE: string[] = [];
const matchCache = new WeakMap<Record<string, Card>, { key: string; shown: ReadonlySet<string> }>();
const columnCache = new WeakMap<string[], { shown: ReadonlySet<string>; ids: string[] }>();
const listsCache = new WeakMap<CardIds, { shown: ReadonlySet<string>; lists: CardIds }>();
const filterCache = new WeakMap<
  BoardFilter,
  WeakMap<BoardSnapshot["stickers"], { filter: BoardFilter; key: string }>
>();

/** Фильтр по полям, видимым на доске, и его ключ для кешей. */
function effective(filter: BoardFilter, stickers: BoardSnapshot["stickers"]) {
  let byStickers = filterCache.get(filter);
  if (!byStickers) {
    byStickers = new WeakMap();
    filterCache.set(filter, byStickers);
  }
  const hit = byStickers.get(stickers);
  if (hit) return hit;
  const visible = new Set(stickers.filter((sticker) => sticker.visible).map((sticker) => sticker.id));
  const pruned = forVisible(filter, visible);
  const made = { filter: pruned, key: JSON.stringify(pruned) };
  byStickers.set(stickers, made);
  return made;
}

/** Id карточек, которые проходят фильтр, или null, если фильтр ничего не отсеивает. */
export function shownSet(s: BoardSnapshot, filter: BoardFilter, today: string): ReadonlySet<string> | null {
  const { filter: active, key } = effective(filter, s.stickers);
  if (!isFiltering(active)) return null;
  const fullKey = `${key}|${today}`;
  const hit = matchCache.get(s.cards);
  if (hit?.key === fullKey) return hit.shown;
  const texts = s.stickers.filter((sticker) => sticker.kind === "text").map((sticker) => sticker.id);
  const shown = new Set(
    Object.values(s.cards)
      .filter((card) => cardMatches(card, active, today, texts))
      .map((card) => card.id),
  );
  matchCache.set(s.cards, { key: fullKey, shown });
  return shown;
}

function shownIn(ids: string[], shown: ReadonlySet<string>) {
  const hit = columnCache.get(ids);
  if (hit?.shown === shown) return hit.ids;
  const visible = ids.filter((id) => shown.has(id));
  columnCache.set(ids, { shown, ids: visible });
  return visible;
}

/** Фильтр доски, каким он действует (поля, скрытые с карточек, не фильтруют). */
export function useActiveFilter() {
  const filter = useFilterAddress();
  return useBoardSelector((s) => effective(filter, s.stickers).filter);
}

/** Карточки колонки, которые видны под фильтром. */
export function useVisibleCardIds(columnId: string) {
  const filter = useFilterAddress();
  const today = useToday();
  return useBoardSelector((s) => {
    const ids = s.cardIds[columnId] ?? NONE;
    const shown = shownSet(s, filter, today);
    return shown ? shownIn(ids, shown) : ids;
  });
}

/** Сколько карточек видно на доске и сколько всего; `filtering` — отсеивает ли фильтр что-нибудь. */
export function useShownCount() {
  const filter = useFilterAddress();
  const today = useToday();
  const total = useBoardSelector((s) => Object.values(s.cardIds).reduce((sum, ids) => sum + ids.length, 0));
  const shown = useBoardSelector((s) => {
    const set = shownSet(s, filter, today);
    return set === null
      ? null
      : Object.values(s.cardIds).reduce((sum, ids) => sum + ids.filter((id) => set.has(id)).length, 0);
  });
  return { total, shown: shown ?? total, filtering: shown !== null };
}

/** Видимые карточки всех колонок — для списка и таблицы. */
export function useVisibleCardLists(): CardIds {
  const filter = useFilterAddress();
  const today = useToday();
  return useBoardSelector((s) => {
    const shown = shownSet(s, filter, today);
    if (!shown) return s.cardIds;
    const hit = listsCache.get(s.cardIds);
    if (hit?.shown === shown) return hit.lists;
    const lists = visibleIds(s.cardIds, shown);
    listsCache.set(s.cardIds, { shown, lists });
    return lists;
  });
}
