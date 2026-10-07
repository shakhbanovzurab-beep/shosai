"use client";

import type { PollingResource } from "@/lib/polling-resource";

/**
 * Adds a steady refresh to a polling resource: every `intervalMs` while someone is subscribed and
 * the tab is visible. A hidden tab stops the timer; coming back refreshes at once and restarts it.
 */
export function withLiveRefresh<T>(resource: PollingResource<T>, intervalMs: number): PollingResource<T> {
  let subscribers = 0;
  let timer: ReturnType<typeof setInterval> | undefined;

  const stop = () => {
    clearInterval(timer);
    timer = undefined;
  };
  const start = () => {
    stop();
    timer = setInterval(() => void resource.refresh(), intervalMs);
  };
  const onVisibilityChange = () => {
    if (document.visibilityState === "hidden") return stop();
    void resource.refresh();
    start();
  };

  return {
    ...resource,
    subscribe(listener: () => void) {
      const unsubscribe = resource.subscribe(listener);
      subscribers += 1;
      if (subscribers === 1) {
        document.addEventListener("visibilitychange", onVisibilityChange);
        if (document.visibilityState === "visible") start();
      }
      return () => {
        unsubscribe();
        subscribers -= 1;
        if (subscribers === 0) {
          document.removeEventListener("visibilitychange", onVisibilityChange);
          stop();
        }
      };
    },
  };
}
