"use client";

import { useEffect, useEffectEvent } from "react";

/*
 * Вопросы к Leo из других мест кабинета, например из ⌘K: виджет Leo на странице открывается и берёт вопрос
 * в свой чат. Виджет один на панель (PanelLayout), поэтому слушатель обычно один.
 */

type Listener = (question: string) => void;

const listeners = new Set<Listener>();

/** Открывает Leo с вопросом; false — на странице нет виджета, и вопрос никуда не ушёл. */
export function askLeo(question: string): boolean {
  const text = question.trim();
  if (text === "" || listeners.size === 0) return false;
  for (const listener of listeners) listener(text);
  return true;
}

/** Подписка на вопросы; ответ снимает её. */
export function listenForQuestions(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Виджет Leo принимает вопросы, пока он на странице. */
export function useLeoQuestions(onQuestion: Listener) {
  const take = useEffectEvent(onQuestion);
  useEffect(() => listenForQuestions((question) => take(question)), []);
}
