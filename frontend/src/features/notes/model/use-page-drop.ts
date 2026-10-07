"use client";

import * as React from "react";

import { useLocale, useTranslations } from "next-intl";

import { filterRecordings } from "./recordings";

/** Lets a file be dropped anywhere on the page, with an overlay while it is dragged over. */
export function usePageDrop(onFiles: (files: File[]) => void) {
  const t = useTranslations("notes");
  const locale = useLocale();
  const [isDragging, setIsDragging] = React.useState(false);
  const depth = React.useRef(0);
  const hasFiles = (event: React.DragEvent) => event.dataTransfer.types.includes("Files");

  const handlers = {
    onDragEnter: (event: React.DragEvent) => {
      if (!hasFiles(event)) return;
      depth.current += 1;
      setIsDragging(true);
    },
    onDragLeave: (event: React.DragEvent) => {
      if (!hasFiles(event)) return;
      depth.current -= 1;
      if (depth.current === 0) setIsDragging(false);
    },
    onDragOver: (event: React.DragEvent) => {
      if (hasFiles(event)) event.preventDefault();
    },
    onDrop: (event: React.DragEvent) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      depth.current = 0;
      setIsDragging(false);
      const accepted = filterRecordings(event.dataTransfer.files, t, locale);
      if (accepted.length > 0) onFiles(accepted);
    },
  };

  return { isDragging, handlers };
}
