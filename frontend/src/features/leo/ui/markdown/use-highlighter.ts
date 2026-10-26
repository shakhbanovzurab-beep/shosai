"use client";

import { useSyncExternalStore } from "react";

type Highlighter = typeof import("./code-highlight");

let loaded: Highlighter | null = null;
let loading: Promise<void> | null = null;
const waiting = new Set<() => void>();

function load() {
  if (loading !== null) return;
  loading = import("./code-highlight").then(
    (module) => {
      loaded = module;
      for (const notify of waiting) notify();
    },
    (error: unknown) => {
      // Без подсветки код читается текстом; следующий блок кода попробует загрузить её снова.
      loading = null;
      console.warn("Leo: подсветка кода не загрузилась", error);
    },
  );
}

function subscribe(notify: () => void) {
  waiting.add(notify);
  if (loaded === null) load();
  return () => {
    waiting.delete(notify);
  };
}

const current = () => loaded;

/** Подсветка кода, загруженная с первым блоком кода; null — пока грузится или не загрузилась. */
export const useHighlighter = () => useSyncExternalStore(subscribe, current, current);
