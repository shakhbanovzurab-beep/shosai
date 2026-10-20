import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { notesApi } from "../api/notes-api";
import type { NoteFolder } from "../domain/types";
import { countsOf, folderOf } from "./library-cards";
import { patchCard, refreshLibraries } from "./library-resource";
import { patchMeeting, refreshMeeting } from "./meeting-resource";
import { describeNoteError } from "./problem-words";
import type { NotesWords } from "./words";

/*
 * Папки человека и счётчики библиотеки с сервера. Папки делит библиотека и страница встречи, поэтому перенос на
 * одной сразу виден на другой. Изменение показывается сразу; сбой говорит тостом и перечитывает данные.
 */

async function everyFolder(): Promise<NoteFolder[]> {
  const folders: NoteFolder[] = [];
  let cursor: string | undefined;
  do {
    const page = await notesApi.folders(cursor);
    folders.push(...page.items.map(folderOf));
    cursor = page.next_cursor ?? undefined;
  } while (cursor);
  return folders;
}

const foldersResource = createPollingResource(everyFolder);
const countsResource = createPollingResource(async () => countsOf(await notesApi.counts()));

export const useFolders = () => usePollingResource(foldersResource);
export const useLibraryCounts = () => usePollingResource(countsResource);
export const refreshCounts = () => void countsResource.refresh();

const failed = (error: unknown, t: NotesWords) => toast.error(describeNoteError(error, t));

export const folderActions = {
  /** Новая папка с именем, которое ввёл человек, или с именем по умолчанию на его языке; null при отказе. */
  async create(name: string, t: NotesWords): Promise<NoteFolder | null> {
    try {
      const folder = folderOf(await notesApi.createFolder(name));
      foldersResource.update((folders) => [...folders, folder]);
      return folder;
    } catch (error) {
      failed(error, t);
      return null;
    }
  },
  async rename(id: string, name: string, t: NotesWords) {
    foldersResource.update((folders) => folders.map((folder) => (folder.id === id ? { ...folder, name } : folder)));
    try {
      await notesApi.renameFolder(id, name);
    } catch (error) {
      failed(error, t);
      void foldersResource.refresh();
    }
  },
  /** Удаляет папку; её встречи остаются, без папки. */
  async remove(id: string, t: NotesWords) {
    foldersResource.update((folders) => folders.filter((folder) => folder.id !== id));
    try {
      await notesApi.removeFolder(id);
    } catch (error) {
      failed(error, t);
      void foldersResource.refresh();
    }
    refreshLibraries();
    refreshCounts();
  },
  /** Кладёт встречу в папку или вынимает из неё (null) — в библиотеке и на странице встречи. */
  async move(noteId: string, target: NoteFolder | null, t: NotesWords) {
    patchCard(noteId, (card) => ({ ...card, folderId: target?.id }));
    patchMeeting(noteId, (page) => ({ ...page, folderId: target?.id }));
    try {
      await notesApi.file(noteId, target?.id ?? null);
      toast.success(target ? t("folders.movedTo", { folder: target.name }) : t("folders.removedFrom"));
    } catch (error) {
      failed(error, t);
      void refreshMeeting(noteId);
    }
    refreshLibraries();
    refreshCounts();
  },
};
