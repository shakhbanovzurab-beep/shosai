"use client";

import { useRef, useState } from "react";

export type AutosaveStatus = "idle" | "pending" | "saving" | "error";

/**
 * Saves `value` a short pause after the last change, or at once on `flush()` (blur, Cmd/Ctrl+S).
 * Saves run one at a time, so an older request can never land after a newer one. `onError` hears about a
 * failed save with a `retry` that goes through the same queue, for screens that show no save status.
 */
export function useAutosave(
  save: (value: string) => Promise<void>,
  delayMs = 800,
  onError?: (retry: () => void, error: unknown) => void,
) {
  const [status, setStatus] = useState<AutosaveStatus>("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const latest = useRef<string | null>(null);
  // Text whose save failed; sent again by Retry unless newer text has been typed since.
  const failed = useRef<string | null>(null);
  const queue = useRef<Promise<void> | null>(null);

  const run = () => {
    clearTimeout(timer.current);
    const value = latest.current ?? failed.current;
    if (value === null) return;
    latest.current = null;
    failed.current = null;
    setStatus("saving");
    queue.current = (queue.current ?? Promise.resolve()).then(() =>
      save(value).then(
        () => setStatus(latest.current === null ? "idle" : "pending"),
        (error: unknown) => {
          failed.current = value;
          setStatus("error");
          onError?.(run, error);
        },
      ),
    );
  };

  return {
    status,
    /** Queues `value` to be saved after the pause. */
    schedule(value: string) {
      latest.current = value;
      setStatus("pending");
      clearTimeout(timer.current);
      timer.current = setTimeout(run, delayMs);
    },
    /** Saves whatever is queued right now. */
    flush: run,
  };
}
