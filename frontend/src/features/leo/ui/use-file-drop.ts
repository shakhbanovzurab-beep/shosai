import * as React from "react";

/**
 * Файлы, перетащенные на панель: счётчик входов не даёт подсказке мигать над вложенными элементами. Выключенное
 * перетаскивание (Leo, к которому файлы не приложить) ничего не перехватывает.
 */
export function useFileDrop(enabled: boolean, onFiles: (files: FileList) => void) {
  const [isDragging, setIsDragging] = React.useState(false);
  const depth = React.useRef(0);
  const carriesFiles = (event: React.DragEvent) => enabled && event.dataTransfer.types.includes("Files");

  const handlers = {
    onDragEnter: (event: React.DragEvent) => {
      if (!carriesFiles(event)) return;
      depth.current += 1;
      setIsDragging(true);
    },
    onDragLeave: (event: React.DragEvent) => {
      if (!carriesFiles(event)) return;
      depth.current -= 1;
      if (depth.current === 0) setIsDragging(false);
    },
    onDragOver: (event: React.DragEvent) => {
      if (carriesFiles(event)) event.preventDefault();
    },
    onDrop: (event: React.DragEvent) => {
      if (!carriesFiles(event)) return;
      event.preventDefault();
      depth.current = 0;
      setIsDragging(false);
      onFiles(event.dataTransfer.files);
    },
  };
  return { isDragging, handlers };
}
