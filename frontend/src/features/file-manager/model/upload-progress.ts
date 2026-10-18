"use client";

import { useSyncExternalStore } from "react";

import { batchPercent } from "../domain/upload-parts";

/*
 * How far the uploads running now got, for every button that started one (File Manager, Knowledge). Each
 * batch reports the bytes its files have sent; the snapshot is how many files are on their way and the
 * percent of all their bytes sent.
 */

export type UploadProgress = { files: number; percent: number };

const IDLE: UploadProgress = { files: 0, percent: 0 };
const batches = new Map<number, { sizes: number[]; sent: number[] }>();
const listeners = new Set<() => void>();
let snapshot = IDLE;
let nextBatch = 0;

function emit() {
  const sizes = [...batches.values()].flatMap((batch) => batch.sizes);
  const sent = [...batches.values()].flatMap((batch) => batch.sent);
  snapshot = sizes.length === 0 ? IDLE : { files: sizes.length, percent: batchPercent(sent, sizes) };
  for (const listener of listeners) listener();
}

/** A batch of files on their way: report each file's bytes sent, then finish it. */
export function startBatch(sizes: number[]) {
  const id = nextBatch++;
  batches.set(id, { sizes, sent: sizes.map(() => 0) });
  emit();
  return {
    sent(index: number, bytes: number) {
      const batch = batches.get(id);
      if (!batch) return;
      batch.sent[index] = bytes;
      emit();
    },
    finish() {
      batches.delete(id);
      emit();
    },
  };
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

export const useUploadProgress = () =>
  useSyncExternalStore(
    subscribe,
    () => snapshot,
    () => IDLE,
  );
