"use client";

import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";
import { inDomain } from "@/lib/resource-domains";

import { memoryApi } from "../api/memory-api";
import type { FactsPage, MemoryFact } from "../domain/contract";
import { failed, type MemoryWords } from "./fact-actions";
import { factsResource } from "./facts-resource";

/*
 * Кандидаты, перенесённые из прежней памяти (MM-D8): не попадают в ежедневное «Запомнить это?», а лежат своим
 * списком, который человек разбирает, когда захочет, — по одному или «Не запоминать их» разом.
 */

export const importedResource = inDomain(
  "memory",
  createPollingResource<FactsPage>(() => memoryApi.imported(null)),
);

export const useImported = () => usePollingResource(importedResource);

export async function moreImported() {
  const state = importedResource.getSnapshot();
  if (state.status !== "ready" || state.data.next_cursor === null) return;
  const page = await memoryApi.imported(state.data.next_cursor);
  importedResource.update((data) => ({ ...page, items: [...data.items, ...page.items] }));
}

const without = (fact: MemoryFact) =>
  importedResource.update((data) => ({ ...data, items: data.items.filter((f) => f.id !== fact.id) }));

/** «Запомнить» или «Не запоминать» один перенесённый факт. */
export async function answerImported(fact: MemoryFact, remember: boolean, { t }: MemoryWords) {
  without(fact);
  try {
    if (remember) await memoryApi.accept(fact.id);
    else await memoryApi.forget(fact.id);
  } catch (error) {
    failed(error, t("failed.save"));
    void importedResource.reload();
    return;
  }
  void factsResource.reload();
}

/** «Не запоминать их»: все перенесённые уходят разом; после подтверждения в диалоге. */
export async function turnDownImported({ t }: MemoryWords) {
  try {
    await memoryApi.turnDownImported();
  } catch (error) {
    failed(error, t("failed.save"));
    return;
  }
  importedResource.update((data) => ({ ...data, items: [], next_cursor: null }));
  void factsResource.reload();
  toast.success(t("imported.done"));
}
