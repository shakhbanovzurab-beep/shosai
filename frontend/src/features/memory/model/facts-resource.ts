"use client";

import { useSyncExternalStore } from "react";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";
import { inDomain } from "@/lib/resource-domains";

import { memoryApi } from "../api/memory-api";
import type { FactsPage, FactsQuery, MemoryFact } from "../domain/contract";

/*
 * Загруженные страницы фактов выбранного вида и слов: фильтрует сервер, поэтому поиск и вид покрывают всю память,
 * а не только загруженное. Счётчики строки настроек — с сервера, по всей памяти. Leo, забывший факт, называет
 * домен `memory`, и показанный список перечитывается.
 */

const EVERYTHING: FactsQuery = { kind: null, words: "" };

let query = EVERYTHING;
const listeners = new Set<() => void>();

export const factsResource = inDomain(
  "memory",
  createPollingResource<FactsPage>(() => memoryApi.list(query, null)),
);

export const useFacts = () => usePollingResource(factsResource);

/** Новый вид или слова: первая страница читается заново. */
export function setFactsQuery(next: FactsQuery) {
  if (next.kind === query.kind && next.words === query.words) return;
  query = next;
  for (const listener of listeners) listener();
  void factsResource.reload();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

export const useFactsQuery = () =>
  useSyncExternalStore(
    subscribe,
    () => query,
    () => EVERYTHING,
  );

/** Дописывает следующую страницу к уже загруженным. */
export async function loadMoreFacts() {
  const state = factsResource.getSnapshot();
  if (state.status !== "ready" || state.data.next_cursor === null) return;
  const page = await memoryApi.list(query, state.data.next_cursor);
  factsResource.update((data) => ({ ...page, items: [...data.items, ...page.items] }));
}

/** Локальная правка списка: заменить, убрать или вернуть факт; счётчики меняет `count`. */
export const changeFacts = (change: (facts: MemoryFact[]) => MemoryFact[]) =>
  factsResource.update((data) => ({ ...data, items: change(data.items) }));

/** Сдвиг счётчиков после правки, до следующего чтения. */
export const count = (active: number, candidates: number) =>
  factsResource.update((data) => ({
    ...data,
    counts: {
      ...data.counts,
      active: Math.max(0, data.counts.active + active),
      candidates: Math.max(0, data.counts.candidates + candidates),
    },
  }));

/** После «Забыть всё»: ни фактов, ни кандидатов; перенесённые из прежней памяти тоже ушли. */
export const clearFacts = () =>
  factsResource.update((data) => ({
    ...data,
    items: [],
    next_cursor: null,
    counts: { active: 0, candidates: 0, imported: 0 },
  }));
