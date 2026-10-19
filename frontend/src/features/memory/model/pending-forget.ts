"use client";

import { useSyncExternalStore } from "react";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";

import { memoryApi } from "../api/memory-api";
import type { MemoryFact } from "../domain/contract";
import type { MemoryWords } from "./fact-actions";
import { changeFacts, factsResource } from "./facts-resource";

/*
 * «Забыть» с отменой внутри окна памяти: факт пропадает сразу, а запрос уходит через несколько секунд, если
 * человек не нажал «Отменить». Тост здесь не годится — модальное окно делает всё вокруг недоступным, и кнопку
 * в тосте не нажать. Ожидает одно забывание: следующее отправляет предыдущее сразу.
 */

const UNDO_MS = 5_000;

type Pending = { fact: MemoryFact; words: MemoryWords; timer: ReturnType<typeof setTimeout> };

let pending: Pending | null = null;
const listeners = new Set<() => void>();

const emit = () => {
  for (const listener of listeners) listener();
};

/** Отправляет ожидающее забывание сейчас. */
export function commitForget() {
  if (!pending) return;
  const { fact, words, timer } = pending;
  clearTimeout(timer);
  pending = null;
  emit();
  memoryApi.forget(fact.id).catch((error: unknown) => {
    toast.error(words.t("failed.forget"), { description: apiErrorDescription(error) });
    void factsResource.refresh();
  });
}

export function forgetFact(fact: MemoryFact, words: MemoryWords) {
  commitForget();
  changeFacts((facts) => facts.filter((f) => f.id !== fact.id));
  pending = { fact, words, timer: setTimeout(commitForget, UNDO_MS) };
  emit();
}

export function undoForget() {
  if (!pending) return;
  const { fact, timer } = pending;
  clearTimeout(timer);
  pending = null;
  changeFacts((facts) => [...facts.filter((f) => f.id !== fact.id), fact]);
  emit();
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
