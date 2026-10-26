"use client";

import { useSyncExternalStore } from "react";

/*
 * Тяжёлые части ответа Leo — подсветка кода и формулы — грузятся отдельными кусками с первым блоком, которому они
 * нужны. Пока кусок грузится или если он не загрузился, место показывает исходник; следующий блок пробует снова.
 */

function lazyModule<T>(load: () => Promise<T>, failure: string): () => T | null {
  let loaded: T | null = null;
  let loading = false;
  const waiting = new Set<() => void>();

  const start = () => {
    if (loading) return;
    loading = true;
    load().then(
      (module) => {
        loaded = module;
        for (const notify of waiting) notify();
      },
      (error: unknown) => {
        loading = false;
        console.warn(failure, error);
      },
    );
  };
  const subscribe = (notify: () => void) => {
    waiting.add(notify);
    if (loaded === null) start();
    return () => {
      waiting.delete(notify);
    };
  };
  const current = () => loaded;

  return function useLazyModule() {
    return useSyncExternalStore(subscribe, current, current);
  };
}

/** Подсветка кода; null — пока грузится или не загрузилась. */
export const useHighlighter = lazyModule(() => import("./code-highlight"), "Leo: подсветка кода не загрузилась");

/** Формулы KaTeX; null — пока грузятся или не загрузились. */
export const useMath = lazyModule(() => import("./math-render"), "Leo: формулы не загрузились");

/** Диаграммы Mermaid; null — пока грузятся или не загрузились. */
export const useDiagrams = lazyModule(() => import("./diagram-render"), "Leo: диаграммы не загрузились");
