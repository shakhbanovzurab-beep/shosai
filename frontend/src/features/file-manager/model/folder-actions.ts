"use client";

import { toast } from "sonner";

import { filesApi } from "../api/files-api";
import type { FileFolder, FolderUpdate } from "../domain/contract";
import { filesResource, pendingDeletes } from "./files-resource";
import { describeError } from "./problem-words";
import type { FileActionWords } from "./words";

/*
 * Changes to folders. Changing whether Leo reads a folder changes its files, so those re-read from the server.
 * Toasts are worded with the `words` the calling component passes in (`useFileActionWords`).
 */

async function patch(folder: FileFolder, change: FolderUpdate, failure: string, words: FileActionWords) {
  try {
    const next = await filesApi.updateFolder(folder.id, change);
    filesResource.update((data) => ({ ...data, folders: data.folders.map((f) => (f.id === next.id ? next : f)) }));
    if (change.leo !== undefined) await filesResource.refresh();
    return next;
  } catch (error) {
    toast.error(failure, { description: describeError(error, words) });
    return null;
  }
}

export async function createFolder(name: string, words: FileActionWords) {
  try {
    const folder = await filesApi.createFolder(name);
    filesResource.update((data) => ({ ...data, folders: [...data.folders, folder] }));
  } catch (error) {
    toast.error(words.t("folderCreateFailed"), { description: describeError(error, words) });
  }
}

export const renameFolder = (folder: FileFolder, name: string, words: FileActionWords) =>
  patch(folder, { name }, words.t("folderRenameFailed"), words);

/** Leo reads every readable file in the folder, including ones added later. `quiet`: the caller confirms. */
export async function setFolderLeo(folder: FileFolder, on: boolean, words: FileActionWords, quiet = false) {
  const { t, common } = words;
  const next = await patch(folder, { leo: on }, on ? t("leoFolderFailed") : t("folderUpdateFailed"), words);
  if (!next) return false;
  if (quiet) return true;
  if (on) toast.success(t("leoFolderOn", { name: folder.name }), { description: t("leoFolderOnDescription") });
  else
    toast(t("leoFolderOff", { name: folder.name }), {
      description: t("leoFolderOffDescription"),
      action: {
        label: common("actions.undo"),
        onClick: () => void patch(folder, { leo: true }, t("undoFailed"), words),
      },
    });
  return true;
}

/** Hides the folder now (its files show in My files) and deletes it once the toast closes without Undo. */
export function deleteFolder(folder: FileFolder, fileCount: number, words: FileActionWords) {
  const { t, common } = words;
  let settled = false;
  pendingDeletes.folders.add(folder.id);
  filesResource.update((data) => ({
    folders: data.folders.filter((f) => f.id !== folder.id),
    files: data.files.map((f) => (f.folder_id === folder.id ? { ...f, folder_id: null } : f)),
  }));
  const commit = () => {
    if (settled) return;
    settled = true;
    filesApi.removeFolder(folder.id).then(
      () => {
        pendingDeletes.folders.delete(folder.id);
        // Files that Leo read only through the folder stop being used.
        if (folder.leo) void filesResource.refresh();
      },
      (error: unknown) => {
        pendingDeletes.folders.delete(folder.id);
        toast.error(t("folderDeleteFailed", { name: folder.name }), { description: describeError(error, words) });
        void filesResource.refresh();
      },
    );
  };
  toast(t("folderDeleted", { name: folder.name }), {
    description: fileCount ? t("folderDeletedFiles", { count: fileCount }) : undefined,
    action: {
      label: common("actions.undo"),
      onClick: () => {
        settled = true;
        pendingDeletes.folders.delete(folder.id);
        void filesResource.refresh();
      },
    },
    onAutoClose: commit,
    onDismiss: commit,
  });
}
