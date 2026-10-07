"use client";

import { useRef, useState } from "react";

import { errorMessage } from "@/lib/errors";

export type AutosaveStatus = "idle" | "pending" | "saving" | "error";

/**
 * Saves the latest value a short pause after the last change, or at once on `flush()`. Saves run one
 * at a time, so an older draft can never land after a newer one. `flush()` resolves to whether
 * everything queued so far reached the server, which publishing relies on.
 */
export function useDraftAutosave<T>(save: (value: T) => Promise<void>, delayMs = 800) {
  const [status, setStatus] = useState<AutosaveStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const latest = useRef<{ value: T } | null>(null);
  // A value whose save failed; sent again by flush() unless a newer one has been queued since.
  const failed = useRef<{ value: T } | null>(null);
  const queue = useRef<Promise<void> | null>(null);

  const run = () => {
    clearTimeout(timer.current);
    const next = latest.current ?? failed.current;
    if (next === null) return;
    latest.current = null;
    failed.current = null;
    setStatus("saving");
    queue.current = (queue.current ?? Promise.resolve()).then(() =>
      save(next.value).then(
        () => {
          setError(null);
          setStatus(latest.current === null ? "idle" : "pending");
        },
        (reason: unknown) => {
          if (latest.current === null) failed.current = next;
          setError(errorMessage(reason) ?? "Не удалось сохранить.");
          setStatus("error");
        },
      ),
    );
  };

  return {
    status,
    error,
    /** Queues `value` to be saved after the pause. */
    schedule(value: T) {
      latest.current = { value };
      setStatus("pending");
      clearTimeout(timer.current);
      timer.current = setTimeout(run, delayMs);
    },
    /** Saves whatever is queued right now and waits for every save in flight. */
    async flush(): Promise<boolean> {
      run();
      await queue.current;
      return failed.current === null && latest.current === null;
    },
    /** Drops anything not yet sent (e.g. before the draft is replaced) and waits for saves in flight. */
    async discard() {
      clearTimeout(timer.current);
      latest.current = null;
      failed.current = null;
      await queue.current;
      setError(null);
      setStatus("idle");
    },
  };
}
