"use client";

import { useSyncExternalStore } from "react";

import { memoryApi } from "../api/memory-api";
import type { MemoryFact } from "../domain/contract";
import { failed, type MemoryWords } from "./fact-actions";
import { changeFacts, count, factsResource } from "./facts-resource";

/*
 * «Забыть» с отменой внутри окна памяти: факт забывается на сервере сразу, а «Отменить» в подвале окна несколько
 * секунд возвращает его (сервер восстанавливает забытое в течение суток). Тост здесь не годится — модальное окно
 * делает всё вокруг недоступным, и кнопку в тосте не нажать. Отменить можно последнее забывание.
 */

const UNDO_MS = 5_000;

type Pending = { fact: MemoryFact; words: MemoryWords; timer: ReturnType<typeof setTimeout> };

let pending: Pending | null = null;
const listeners = new Set<() => void>();

const emit = () => {
  for (const listener of listeners) listener();
};

function settle() {
  if (pending) clearTimeout(pending.timer);
  pending = null;
  emit();
}

export async function forgetFact(fact: MemoryFact, words: MemoryWords) {
  settle();
  changeFacts((facts) => facts.filter((f) => f.id !== fact.id));
  count(-1, 0);
  try {
    await memoryApi.forget(fact.id);
  } catch (error) {
    changeFacts((facts) => [...facts.filter((f) => f.id !== fact.id), fact]);
    count(1, 0);
    failed(error, words.t("failed.forget"));
    return;
  }
  pending = { fact, words, timer: setTimeout(settle, UNDO_MS) };
  emit();
}

export async function undoForget() {
  if (!pending) return;
  const { fact, words } = pending;
  settle();
  try {
    const back = await memoryApi.restore(fact.id);
    changeFacts((facts) => [...facts.filter((f) => f.id !== back.id), back]);
    count(1, 0);
  } catch (error) {
    failed(error, words.t("failed.save"));
    void factsResource.refresh();
  }
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** Факт, который можно вернуть, или null. */
export const usePendingForget = () =>
  useSyncExternalStore(
    subscribe,
    () => pending?.fact ?? null,
    () => null,
  );
