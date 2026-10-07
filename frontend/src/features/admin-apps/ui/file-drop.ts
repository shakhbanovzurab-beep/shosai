"use client";

import { type DragEvent, useRef, useState } from "react";

const hasFiles = (event: DragEvent) => event.dataTransfer.types.includes("Files");

/**
 * Drag-and-drop of a single file onto an element. Counts enter/leave so moving over children
 * doesn't flicker. Drops are always swallowed (so the browser never navigates to the file), but
 * only passed on while `enabled`.
 */
export function useFileDrop(onFile: (file: File) => void, enabled = true) {
  const [isDragging, setIsDragging] = useState(false);
  const depth = useRef(0);

  const handlers = {
    onDragEnter: (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.stopPropagation();
      depth.current += 1;
      if (enabled) setIsDragging(true);
    },
    onDragLeave: (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.stopPropagation();
      depth.current = Math.max(0, depth.current - 1);
      if (depth.current === 0) setIsDragging(false);
    },
    onDragOver: (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      event.stopPropagation();
      event.dataTransfer.dropEffect = enabled ? "copy" : "none";
    },
    onDrop: (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      event.stopPropagation();
      depth.current = 0;
      setIsDragging(false);
      const file = event.dataTransfer.files[0];
      if (enabled && file) onFile(file);
    },
  };

  return { isDragging: isDragging && enabled, handlers };
}
