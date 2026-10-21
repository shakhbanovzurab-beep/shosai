"use client";

import { type DragEvent, useState } from "react";

const carriesFiles = (event: DragEvent) => event.dataTransfer.types.includes("Files");

/** Файлы, брошенные на раздел: подсветка, пока они над ним, и сами файлы при броске. Выключено — ничего не ловит. */
export function useFileDrop(enabled: boolean, onFiles: (files: File[]) => void) {
  const [over, setOver] = useState(false);
  if (!enabled) return { over: false, dropProps: {} };
  return {
    over,
    dropProps: {
      onDragOver: (event: DragEvent) => {
        if (!carriesFiles(event)) return;
        event.preventDefault();
        setOver(true);
      },
      onDragLeave: (event: DragEvent) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOver(false);
      },
      onDrop: (event: DragEvent) => {
        if (!carriesFiles(event)) return;
        event.preventDefault();
        setOver(false);
        onFiles([...event.dataTransfer.files]);
      },
    },
  };
}
