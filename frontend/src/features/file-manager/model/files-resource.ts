"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { filesApi } from "../api/files-api";
import { type FilesResponse, IN_PROGRESS } from "../domain/contract";

/*
 * The account's files, shared by File Manager and Knowledge. It re-reads while Leo is indexing
 * something. Files and folders waiting out their Undo toast stay hidden even when a poll brings them back.
 */

const pending = { files: new Set<string>(), folders: new Set<string>() };

function withoutPending(data: FilesResponse): FilesResponse {
  if (pending.files.size === 0 && pending.folders.size === 0) return data;
  return {
    folders: data.folders.filter((f) => !pending.folders.has(f.id)),
    files: data.files
      .filter((f) => !pending.files.has(f.id))
      .map((f) => (f.folder_id && pending.folders.has(f.folder_id) ? { ...f, folder_id: null } : f)),
  };
}

export const filesResource = createPollingResource(
  async () => withoutPending(await filesApi.list()),
  (data) => data.files.some((f) => f.leo !== null && IN_PROGRESS.has(f.leo.status)),
);

export const pendingDeletes = pending;

export const useFiles = () => usePollingResource(filesResource);
