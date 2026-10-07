"use client";

import { useCallback, useSyncExternalStore } from "react";

import { type FocusTimer, isRunning, remainingMs } from "../domain/focus/timer";

/**
 * The time left in the phase, rounded up to whole seconds, so the clock shows "25:00" the moment it
 * starts and "0:00" exactly when it ends. Re-renders only when the shown second changes.
 */
export function useTimeLeft(timer: FocusTimer) {
  const running = isRunning(timer);
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (!running) return () => undefined;
      const id = window.setInterval(onChange, 200);
      return () => window.clearInterval(id);
    },
    [running],
  );
  const getSnapshot = useCallback(() => Math.ceil(remainingMs(timer, Date.now()) / 1000) * 1000, [timer]);
  return useSyncExternalStore(subscribe, getSnapshot, () => timer.remainingMs);
}
