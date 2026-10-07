"use client";

import { useSyncExternalStore } from "react";

import { setLocalStorageValue } from "@/lib/local-storage.client";

const listeners = new Set<() => void>();

function read(key: string) {
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

/** Whether something was dismissed in this browser (e.g. the setup checklist), and a way to dismiss it. */
export function useDismissed(key: string): [boolean, () => void] {
  const dismissed = useSyncExternalStore(
    (onChange) => {
      listeners.add(onChange);
      return () => listeners.delete(onChange);
    },
    () => read(key),
    () => false,
  );
  const dismiss = () => {
    setLocalStorageValue(key, "1");
    for (const listener of listeners) listener();
  };
  return [dismissed, dismiss];
}
