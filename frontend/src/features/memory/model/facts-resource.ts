"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { memoryApi } from "../api/memory-api";
import type { FactsPage, MemoryFact } from "../domain/contract";

/** Загруженные страницы фактов: первая — сразу, следующие — по «Показать ещё». */
export const factsResource = createPollingResource<FactsPage>(() => memoryApi.list());

export const useFacts = () => usePollingResource(factsResource);

/** Дописывает следующую страницу к уже загруженным. */
export async function loadMoreFacts() {
  const state = factsResource.getSnapshot();
  if (state.status !== "ready" || state.data.next_cursor === null) return;
  const page = await memoryApi.list(state.data.next_cursor);
  factsResource.update((data) => ({ facts: [...data.facts, ...page.facts], next_cursor: page.next_cursor }));
}

/** Локальная правка списка: заменить, убрать или вернуть факт. */
export const changeFacts = (change: (facts: MemoryFact[]) => MemoryFact[]) =>
  factsResource.update((data) => ({ ...data, facts: change(data.facts) }));
