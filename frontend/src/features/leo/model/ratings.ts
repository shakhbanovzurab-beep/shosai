"use client";

import { useSyncExternalStore } from "react";

import { toast } from "sonner";

import { agentApi } from "../api/agent-api";
import type { LeoRating } from "../domain/types";

/*
 * Оценки ответов Leo (AG-D13): нажатие видно сразу, сервер подтверждает его или откатывает с тостом. Повторное
 * нажатие той же оценки снимает её. Здесь — то, что человек нажал, поверх оценки из истории, и стал ли ход
 * оценочным случаем: это знает только ответ на оценку.
 */

type Pressed = { rating: LeoRating | null; shared: boolean; busy: boolean };

let pressed: ReadonlyMap<string, Pressed> = new Map();
const listeners = new Set<() => void>();

function set(messageId: string, next: Pressed | undefined) {
  const copy = new Map(pressed);
  if (next === undefined) copy.delete(messageId);
  else copy.set(messageId, next);
  pressed = copy;
  for (const listener of listeners) listener();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

const snapshot = () => pressed;

/** Оценка ответа, какой её видит человек: нажатая поверх записанной, и ушла ли она в оценочные случаи. */
export function useRating(messageId: string, saved: LeoRating | null) {
  const state = useSyncExternalStore(subscribe, snapshot, snapshot).get(messageId);
  return state ?? { rating: saved, shared: false, busy: false };
}

/** Нажать оценку: та же, что стоит, снимается. Сбой возвращает прежнюю и говорит тостом; ответ — как вышло. */
export async function pressRating(
  messageId: string,
  current: LeoRating | null,
  chosen: LeoRating,
  failed: string,
): Promise<Pressed | undefined> {
  const before = pressed.get(messageId);
  const next = current === chosen ? null : chosen;
  set(messageId, { rating: next, shared: false, busy: true });
  try {
    let shared = false;
    if (next === null) await agentApi.unrate(messageId);
    else shared = (await agentApi.rate(messageId, next)).shared;
    const done = { rating: next, shared, busy: false };
    set(messageId, done);
    return done;
  } catch (error) {
    set(messageId, before);
    toast.error(failed);
    console.warn("Leo: оценка ответа не сохранилась", error);
    return undefined;
  }
}
