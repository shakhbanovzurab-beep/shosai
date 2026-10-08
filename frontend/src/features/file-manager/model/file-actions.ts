"use client";

import { toast } from "sonner";

import { refreshFileShares } from "@/features/workspace/model/resources";
import { apiErrorDescription } from "@/lib/api/error-description";

import { filesApi } from "../api/files-api";
import type { FileItem, FilesResponse, FileUpdate } from "../domain/contract";
import { filesResource, pendingDeletes } from "./files-resource";
import type { FileActionWords } from "./words";

/*
 * Changes to files. Each applies at once where it can, reports failures itself and never throws. Toasts are
 * worded with the `words` the calling component passes in (`useFileActionWords`).
 */

const replaceFile = (next: FileItem) =>
  filesResource.update((data) => ({ ...data, files: data.files.map((f) => (f.id === next.id ? next : f)) }));

const currentFiles = (): FilesResponse | null => {
  const state = filesResource.getSnapshot();
  return state.status === "ready" ? state.data : null;
};

async function patch(id: string, change: FileUpdate, failure: string) {
  try {
    const next = await filesApi.update(id, change);
    replaceFile(next);
    return next;
  } catch (error) {
    toast.error(failure, { description: apiErrorDescription(error) });
    void filesResource.refresh();
    return null;
  }
}

export async function uploadFiles(
  files: File[],
  options: { folderId: string | null; leo: boolean },
  { t }: FileActionWords,
) {
  try {
    const { files: added } = await filesApi.upload(files, options);
    filesResource.update((data) => ({ ...data, files: [...added, ...data.files] }));
    const folder = currentFiles()?.folders.find((f) => f.id === options.folderId);
    const leo = added.some((f) => f.leo);
    let description: string | undefined;
    if (leo) description = added.length === 1 ? t("leoReadingFile") : t("leoReadingFiles");
    if (leo && folder?.leo) description = t("leoReadsFolder", { folder: folder.name });
    const first = added[0];
    const title =
      added.length === 1 && first
        ? t("uploadedFile", { name: first.name })
        : t("uploadedFiles", { count: added.length });
    toast.success(title, { description });
    return true;
  } catch (error) {
    toast.error(t("uploadFailed"), { description: apiErrorDescription(error) });
    return false;
  }
}

export const renameFile = (id: string, name: string, { t }: FileActionWords) => patch(id, { name }, t("renameFailed"));

export const toggleStar = (file: FileItem, { t }: FileActionWords) => {
  replaceFile({ ...file, starred: !file.starred });
  return patch(file.id, { starred: !file.starred }, t("updateFailed"));
};

/** `folderName` is the target as the user reads it: a folder's name, or "My files" in their language. */
export async function moveFile(file: FileItem, folderId: string | null, folderName: string, words: FileActionWords) {
  const { t, common } = words;
  if (file.folder_id === folderId) return;
  replaceFile({ ...file, folder_id: folderId });
  const moved = await patch(file.id, { folder_id: folderId }, t("moveFailed"));
  if (!moved) return;
  toast(t("moved", { name: file.name, folder: folderName }), {
    description: !file.leo && moved.leo ? t("movedLeo") : undefined,
    action: {
      label: common("actions.undo"),
      onClick: () => void patch(file.id, { folder_id: file.folder_id }, t("moveBackFailed")),
    },
  });
}

/** The file's own "Use with Leo". `quiet` leaves the confirmation to a caller changing several at once. */
export async function setFileLeo(file: FileItem, on: boolean, { t }: FileActionWords, quiet = false) {
  const next = await patch(file.id, { leo: on }, on ? t("leoFileFailed") : t("updateFailed"));
  if (!next) return false;
  if (quiet) return true;
  if (on) toast.success(t("leoFileOn", { name: file.name }), { description: t("leoFileOnDescription") });
  else if (next.leo) toast(t("leoFileStillViaFolder", { name: file.name }));
  else toast(t("leoFileOff", { name: file.name }), { description: t("leoFileOffDescription") });
  return true;
}

export async function duplicateFile(file: FileItem, { t }: FileActionWords) {
  try {
    const copy = await filesApi.copy(file.id);
    filesResource.update((data) => {
      const index = data.files.findIndex((f) => f.id === file.id);
      return { ...data, files: data.files.toSpliced(index + 1, 0, copy) };
    });
  } catch (error) {
    toast.error(t("duplicateFailed"), { description: apiErrorDescription(error) });
  }
}

export async function reindexFile(file: FileItem, { t }: FileActionWords) {
  try {
    replaceFile(await filesApi.reindex(file.id));
    toast.success(t("reindexed", { name: file.name }));
  } catch (error) {
    toast.error(t("reindexFailed"), { description: apiErrorDescription(error) });
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
        if (sharedIn) refreshFileShares();
      },
      (error: unknown) => {
        pendingDeletes.files.delete(file.id);
        toast.error(t("deleteFailed", { name: file.name }), { description: apiErrorDescription(error) });
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

/** Hands a shared file over to the workspace: it stays there for good and leaves My files. */
export async function transferFile(file: FileItem, workspace: { id: string; name: string }, { t }: FileActionWords) {
  try {
    await filesApi.transfer(file.id, workspace.id);
    filesResource.update((data) => ({ ...data, files: data.files.filter((f) => f.id !== file.id) }));
    refreshFileShares();
    toast.success(t("transferred", { name: file.name, workspace: workspace.name }), {
      description: t("transferredDescription"),
    });
    return true;
  } catch (error) {
    toast.error(t("transferFailed"), { description: apiErrorDescription(error) });
    return false;
  }
}
