"use client";

import { useSyncExternalStore } from "react";

const MINUTE_MS = 60_000;

/** Ticks on every wall-clock minute, so "live" and "in 5 min" stay right while the page is open. */
function subscribe(onChange: () => void) {
  let timer = 0;
  const schedule = () => {
    timer = window.setTimeout(
      () => {
        onChange();
        schedule();
      },
      MINUTE_MS - (Date.now() % MINUTE_MS),
    );
  };
  schedule();
  return () => window.clearTimeout(timer);
}

const getSnapshot = () => Math.floor(Date.now() / MINUTE_MS) * MINUTE_MS;

/** Now, to the minute; null while server rendering so hydration never mismatches. */
export const useNow = () => useSyncExternalStore<number | null>(subscribe, getSnapshot, () => null);
