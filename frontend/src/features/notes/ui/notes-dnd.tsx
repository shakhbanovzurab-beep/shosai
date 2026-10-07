"use client";

import type * as React from "react";

import {
  DragDropProvider,
  type DragEndEvent,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
} from "@dnd-kit/react";
import { cn } from "cn";
import { GripVertical } from "lucide-react";

const NOTE_TYPE = "note";
const FOLDER_TYPE = "note-folder";

const INTERACTIVE_SELECTOR =
  "input, select, textarea, button, a[href], [contenteditable]:not([contenteditable='false'])";

// By default dnd-kit won't start a drag from a link. Each meeting's title link is stretched over the whole
// card, so that default would block dragging everywhere. Let that link (and plain content) start a drag,
// but keep real controls inside the meeting, like buttons, clickable as usual.
const noteSensors = [
  PointerSensor.configure({
    preventActivation: (event, source) => {
      if (!(event.target instanceof Element)) return false;
      const interactive = event.target.closest(INTERACTIVE_SELECTOR);
      if (!interactive) return false;
      return !(interactive instanceof HTMLAnchorElement && source.element?.contains(interactive));
    },
  }),
  KeyboardSensor,
];

const hasNoteId = (data: unknown): data is { noteId: string } =>
  typeof data === "object" && data !== null && typeof (data as { noteId?: unknown }).noteId === "string";

const hasFolderTarget = (data: unknown): data is { folderId: string | null } =>
  typeof data === "object" && data !== null && "folderId" in data;

interface NotesDndProviderProps {
  readonly titleOf: (noteId: string) => string | undefined;
  readonly onDropOnFolder: (noteId: string, folderId: string | null) => void;
  readonly children: React.ReactNode;
}

/** Drag a meeting from any view onto a folder pill to move it; drop it on "All meetings" to take it out. */
export function NotesDndProvider({ titleOf, onDropOnFolder, children }: NotesDndProviderProps) {
  const handleDragEnd = (event: DragEndEvent) => {
    const { source, target } = event.operation;
    if (event.canceled || !source || !target) return;
    if (hasNoteId(source.data) && hasFolderTarget(target.data))
      onDropOnFolder(source.data.noteId, target.data.folderId);
  };

  return (
    <DragDropProvider onDragEnd={handleDragEnd}>
      {children}
      <DragOverlay dropAnimation={null}>
        {(source) =>
          hasNoteId(source.data) ? (
            <div className="flex w-max max-w-72 cursor-grabbing items-center gap-2 rounded-xl border bg-popover px-3 py-2 text-popover-foreground text-sm shadow-xl">
              <GripVertical className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span dir="auto" className="truncate font-medium">
                {titleOf(source.data.noteId)}
              </span>
            </div>
          ) : null
        }
      </DragOverlay>
    </DragDropProvider>
  );
}

/**
 * Makes a meeting (card, row or timeline entry) draggable. Keyboard and screen-reader users move meetings
 * with the context menu's "Move to folder" instead.
 */
export function DraggableNote({ noteId, children }: { readonly noteId: string; readonly children: React.ReactNode }) {
  const { ref, isDragging } = useDraggable({
    id: `note:${noteId}`,
    type: NOTE_TYPE,
    data: { noteId },
    sensors: noteSensors,
  });

  return (
    <div ref={ref} className={cn("grid cursor-grab active:cursor-grabbing", isDragging && "opacity-40")}>
      {children}
    </div>
  );
}

/** Turns a folder pill into a drop target; `folderId: null` is "All meetings" (no folder). */
export function useFolderDrop(folderId: string | null) {
  const { ref, isDropTarget } = useDroppable({
    id: `note-folder:${folderId ?? "none"}`,
    type: FOLDER_TYPE,
    accept: NOTE_TYPE,
    data: { folderId },
  });
  return { ref, isDropTarget };
}
