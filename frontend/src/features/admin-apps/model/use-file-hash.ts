"use client";

import { useSyncExternalStore } from "react";

import { canHashInBrowser, sha256Hex } from "./sha256";

export type HashState =
  | { status: "hashing" }
  | { status: "done"; value: string }
  /** Plain http (no Web Crypto) or the browser couldn't read the file: the server's checksum is used. */
  | { status: "unavailable" };

type Entry = { state: HashState; promise: Promise<string | null>; listeners: Set<() => void> };

const HASHING: HashState = { status: "hashing" };
const UNAVAILABLE: HashState = { status: "unavailable" };
const entries = new WeakMap<File, Entry>();

/** Starts hashing a file once; later calls share the result. */
function entryFor(file: File): Entry {
  const existing = entries.get(file);
  if (existing) return existing;
  const entry: Entry = { state: HASHING, promise: Promise.resolve(null), listeners: new Set() };
  entries.set(file, entry);
  const settle = (state: HashState) => {
    entry.state = state;
    for (const listener of entry.listeners) listener();
  };
  if (!canHashInBrowser()) {
    entry.state = UNAVAILABLE;
    return entry;
  }
  entry.promise = sha256Hex(file).then(
    (value) => {
      settle({ status: "done", value });
      return value;
    },
    () => {
      settle(UNAVAILABLE);
      return null;
    },
  );
  return entry;
}

/** The browser's SHA-256 of `file`, or null when it can't be computed. */
export const fileHash = (file: File) => entryFor(file).promise;

/** Hashing progress for the selected file; hashing starts when a component subscribes. */
export function useFileHash(file: File | null): HashState | null {
  return useSyncExternalStore(
    (listener) => {
      if (!file) return () => undefined;
      const entry = entryFor(file);
      entry.listeners.add(listener);
      listener();
      return () => entry.listeners.delete(listener);
    },
    () => (file ? (entries.get(file)?.state ?? HASHING) : null),
    () => null,
  );
}
