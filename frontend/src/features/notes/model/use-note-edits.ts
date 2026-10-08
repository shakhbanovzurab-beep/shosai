"use client";

import * as React from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import type { NoteGroup } from "../domain/types";
import { folderActions, folderIdAfterMoves, useFolderMoves } from "./folders-store";

/**
 * Local edits on top of the server's notes: moving a note between folders and deleting it (with undo).
 * They live in client state until notes are backed by an API.
 */
export function useNoteEdits(groups: NoteGroup[]) {
  const t = useTranslations("notes");
  const common = useTranslations("common");
  const moves = useFolderMoves();
  const [deletedIds, setDeletedIds] = React.useState<ReadonlySet<string>>(() => new Set());

  const editedGroups = groups
    .map((group) => ({
      ...group,
      items: group.items
        .filter((note) => !deletedIds.has(note.id))
        .map((note) => (note.id in moves ? { ...note, folderId: folderIdAfterMoves(note, moves) } : note)),
    }))
    .filter((group) => group.items.length > 0);

  const deleteNote = (noteId: string, title: string) => {
    setDeletedIds((current) => new Set(current).add(noteId));
    toast(t("deleted", { title }), {
      action: {
        label: common("actions.undo"),
        onClick: () =>
          setDeletedIds((current) => {
            const next = new Set(current);
            next.delete(noteId);
            return next;
          }),
      },
    });
  };

  const moveNote = (noteId: string, folderId: string | null, folderName: string) =>
    folderActions.move(noteId, folderId, folderName, t);

  return { groups: editedGroups, moveNote, deleteNote };
}
