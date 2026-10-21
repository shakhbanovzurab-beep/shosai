"use client";

import { useSyncExternalStore } from "react";

import { type BoardFilter, NO_FILTER } from "../../domain/filter-contract";
import { filterFromSearch, searchWithFilter } from "../../domain/filter-url";

/*
 * Фильтр доски живёт в адресе (план пакета §4.5): ссылка воспроизводит вид, ничего не прячет доску незаметно в
 * следующий раз. Адрес меняется заменой, без новой записи истории на каждую букву поиска; на изменение подписаны
 * панель фильтра и колонки, а не роутер.
 */

const listeners = new Set<() => void>();
let cached: { key: string; filter: BoardFilter } = { key: "", filter: NO_FILTER };

const keyOf = (filter: BoardFilter) => searchWithFilter(new URLSearchParams(), filter).toString();

/** Фильтр из адреса; тот же объект, пока сам фильтр не изменился (смена открытой задачи его не трогает). */
function read(): BoardFilter {
  const filter = filterFromSearch(new URLSearchParams(window.location.search));
  const key = keyOf(filter);
  if (key !== cached.key) cached = { key, filter };
  return cached.filter;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("popstate", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("popstate", listener);
  };
}

export const useFilterAddress = () => useSyncExternalStore(subscribe, read, () => NO_FILTER);

/** Поставить фильтр в адрес; запись истории роутера (её состояние) остаётся той же. */
export function setFilter(change: (filter: BoardFilter) => BoardFilter) {
  const url = new URL(window.location.href);
  const params = searchWithFilter(url.searchParams, change(read()));
  const search = params.toString();
  window.history.replaceState(window.history.state, "", `${url.pathname}${search ? `?${search}` : ""}`);
  for (const listener of listeners) listener();
}

export const clearFilter = () => setFilter(() => NO_FILTER);

/** Убрать фильтр одного своего поля — например, когда поле спрятали с карточек. */
export const dropFieldFilter = (stickerId: string) =>
  setFilter((filter) => {
    const { [stickerId]: _state, ...states } = filter.states;
    const { [stickerId]: _number, ...numbers } = filter.numbers;
    const { [stickerId]: _text, ...texts } = filter.texts;
    return { ...filter, states, numbers, texts };
  });
