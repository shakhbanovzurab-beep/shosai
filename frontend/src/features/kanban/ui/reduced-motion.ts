"use client";

import { useSyncExternalStore } from "react";

/*
 * Человек попросил систему меньше двигать экран: сортируемые карточки, колонки и подзадачи встают на место без
 * сдвига. dnd-kit двигает их через Web Animations, поэтому общее CSS-правило кабинета их не касается.
 */

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(listener: () => void) {
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", listener);
  return () => media.removeEventListener("change", listener);
}

export const useReducedMotion = () =>
  useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  );

/** Перестановка без анимации — для `useSortable({ transition })`. */
export const STILL = { duration: 0, easing: "linear", idle: false };
