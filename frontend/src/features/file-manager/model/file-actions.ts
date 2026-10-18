"use client";

import { toast } from "sonner";

import { refreshFileShares } from "@/features/workspace/model/resources";
import { saveFile } from "@/lib/save-file";

import { filesApi } from "../api/files-api";
import type { FileItem, FileUpdate } from "../domain/contract";
import { filesResource, pendingDeletes } from "./files-resource";
import { describeError } from "./problem-words";
import { storageResource } from "./storage-resource";
import type { FileActionWords } from "./words";

/*
 * Changes to files. Each applies at once where it can, reports failures itself and never throws. Toasts are
 * worded with the `words` the calling component passes in (`useFileActionWords`).
 */

const replaceFile = (next: FileItem) =>
  filesResource.update((data) => ({ ...data, files: data.files.map((f) => (f.id === next.id ? next : f)) }));

async function patch(id: string, change: FileUpdate, failure: string, words: FileActionWords) {
  try {
    const next = await filesApi.update(id, change);
    replaceFile(next);
    return next;
  } catch (error) {
    toast.error(failure, { description: describeError(error, words) });
    void filesResource.refresh();
    return null;
  }
}

export const renameFile = (id: string, name: string, words: FileActionWords) =>
  patch(id, { name }, words.t("renameFailed"), words);

export const toggleStar = (file: FileItem, words: FileActionWords) => {
  replaceFile({ ...file, starred: !file.starred });
  return patch(file.id, { starred: !file.starred }, words.t("updateFailed"), words);
};

/** `folderName` is the target as the user reads it: a folder's name, or "My files" in their language. */
export async function moveFile(file: FileItem, folderId: string | null, folderName: string, words: FileActionWords) {
  const { t, common } = words;
  if (file.folder_id === folderId) return;
  replaceFile({ ...file, folder_id: folderId });
  const moved = await patch(file.id, { folder_id: folderId }, t("moveFailed"), words);
  if (!moved) return;
  toast(t("moved", { name: file.name, folder: folderName }), {
    description: !file.leo && moved.leo ? t("movedLeo") : undefined,
    action: {
      label: common("actions.undo"),
      onClick: () => void patch(file.id, { folder_id: file.folder_id }, t("moveBackFailed"), words),
    },
  });
}

/** The file's own "Use with Leo". `quiet` leaves the confirmation to a caller changing several at once. */
export async function setFileLeo(file: FileItem, on: boolean, words: FileActionWords, quiet = false) {
  const { t } = words;
  const next = await patch(file.id, { leo: on }, on ? t("leoFileFailed") : t("updateFailed"), words);
  if (!next) return false;
  if (quiet) return true;
  if (on) toast.success(t("leoFileOn", { name: file.name }), { description: t("leoFileOnDescription") });
  else if (next.leo) toast(t("leoFileStillViaFolder", { name: file.name }));
  else toast(t("leoFileOff", { name: file.name }), { description: t("leoFileOffDescription") });
  return true;
}

export async function duplicateFile(file: FileItem, words: FileActionWords) {
  try {
    const copy = await filesApi.copy(file.id);
    filesResource.update((data) => {
      const index = data.files.findIndex((f) => f.id === file.id);
      return { ...data, files: data.files.toSpliced(index + 1, 0, copy) };
    });
    void storageResource.refresh();
  } catch (error) {
    toast.error(words.t("duplicateFailed"), { description: describeError(error, words) });
  }
}

export async function reindexFile(file: FileItem, words: FileActionWords) {
  try {
    replaceFile(await filesApi.reindex(file.id));
    toast.success(words.t("reindexed", { name: file.name }));
  } catch (error) {
    toast.error(words.t("reindexFailed"), { description: describeError(error, words) });
  }
}

/** Saves the file through a 15-minute link on Shosai's address; the edge streams its bytes (FL-D9). */
export async function downloadFile(file: FileItem, words: FileActionWords) {
  try {
    const { url } = await filesApi.download(file.id);
    saveFile(url, file.name);
  } catch (error) {
    toast.error(words.t("downloadFailed", { name: file.name }), { description: describeError(error, words) });
  }
}

/**
 * Hides the file now and deletes it for good once the toast closes without Undo. `sharedIn` lists the
 * workspaces it leaves, already joined for the user's language ("Lumen and Acme"); empty when none.
 */
export function deleteFile(file: FileItem, sharedIn: string, words: FileActionWords) {
  const { t, common } = words;
  let settled = false;
  pendingDeletes.files.add(file.id);
  filesResource.update((data) => ({ ...data, files: data.files.filter((f) => f.id !== file.id) }));
  const commit = () => {
    if (settled) return;
    settled = true;
    filesApi.remove(file.id).then(
      () => {
        pendingDeletes.files.delete(file.id);
        void storageResource.refresh();
        if (sharedIn) refreshFileShares();
      },
      (error: unknown) => {
        pendingDeletes.files.delete(file.id);
        toast.error(t("deleteFailed", { name: file.name }), { description: describeError(error, words) });
        void filesResource.refresh();
      },
    );
  };
  toast(t("deleted", { name: file.name }), {
    description: sharedIn ? t("deletedShared", { workspaces: sharedIn }) : undefined,
    action: {
      label: common("actions.undo"),
      onClick: () => {
        settled = true;
        pendingDeletes.files.delete(file.id);
        void filesResource.refresh();
      },
    },
    onAutoClose: commit,
    onDismiss: commit,
  });
}
