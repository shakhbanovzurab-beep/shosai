"use client";

import { useSyncExternalStore } from "react";

const SECOND_MS = 1000;

function subscribe(onTick: () => void) {
  const timer = window.setInterval(onTick, SECOND_MS);
  return () => window.clearInterval(timer);
}

// Снимок меняется раз в секунду: между тиками React получает то же число и не перерисовывает.
const wholeSecond = () => Math.floor(Date.now() / SECOND_MS) * SECOND_MS;

/** Сколько прошло с `since`, целыми секундами, с тиком раз в секунду, — для живого таймера хода. */
export function useElapsed(since: number): number {
  const now = useSyncExternalStore(subscribe, wholeSecond, wholeSecond);
  return Math.max(0, now - Math.floor(since / SECOND_MS) * SECOND_MS);
}
