import { toast } from "sonner";
import { create } from "zustand";

import { noteFolders } from "../data/meeting-notes";
import { FOLDER_COLOR_CYCLE } from "../domain/folder-colors";
import type { NoteFolder } from "../domain/types";
import type { NotesWords } from "./words";

type FoldersStore = {
  folders: NoteFolder[];
  /** Folder moves made in this session, by note id; null takes a note out of its folder. */
  moves: Readonly<Record<string, string | null>>;
};

// Shared by the library and a note's page, so a move on one shows on the other. Local until notes have an API.
const useFoldersStore = create<FoldersStore>(() => ({ folders: noteFolders, moves: {} }));

export const useNoteFolders = () => useFoldersStore((state) => state.folders);
export const useFolderMoves = () => useFoldersStore((state) => state.moves);

/** The folder a note is in once this session's moves are applied. */
export const folderIdAfterMoves = (note: { id: string; folderId?: string }, moves: FoldersStore["moves"]) =>
  note.id in moves ? (moves[note.id] ?? undefined) : note.folderId;

let folderCounter = 0;

export const folderActions = {
  /** A new folder named `name`: what the user typed, or the default name in the interface language. */
  create: (name: string): NoteFolder => {
    folderCounter += 1;
    const { folders } = useFoldersStore.getState();
    const folder: NoteFolder = {
      id: `folder-${Date.now().toString(36)}-${folderCounter}`,
      name,
      color: FOLDER_COLOR_CYCLE[folders.length % FOLDER_COLOR_CYCLE.length],
    };
    useFoldersStore.setState({ folders: [...folders, folder] });
    return folder;
  },
  rename: (id: string, name: string) =>
    useFoldersStore.setState((state) => ({
      folders: state.folders.map((folder) => (folder.id === id ? { ...folder, name } : folder)),
    })),
  remove: (id: string) =>
    useFoldersStore.setState((state) => ({ folders: state.folders.filter((folder) => folder.id !== id) })),
  /** Moves a note into a folder, or out of any folder with null. */
  move: (noteId: string, folderId: string | null, folderName: string, t: NotesWords) => {
    useFoldersStore.setState((state) => ({ moves: { ...state.moves, [noteId]: folderId } }));
    toast.success(folderId ? t("folders.movedTo", { folder: folderName }) : t("folders.removedFrom"));
  },
};
