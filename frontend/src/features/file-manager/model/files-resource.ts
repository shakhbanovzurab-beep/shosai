"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { filesApi } from "../api/files-api";
import { type FilesResponse, INDEXING } from "../domain/contract";

/*
 * The account's files, shared by File Manager and Knowledge. It re-reads while Leo is indexing something,
 * and for 30 s after the queue changes: a queued file waits for knowledge, which may not pick it up soon, so
 * an open tab doesn't poll the server for as long as the queue stands. Files and folders waiting out their
 * Undo toast stay hidden even when a poll brings them back.
 */

// 20 опросов по 1,5 с: очередь, которая не двигается, перестаёт нагружать сервер через 30 с.
const QUEUED_POLLS = 20;

/** Whether to read the files again: while knowledge indexes one, and `limit` times after the queue changes. */
export function indexingPoller(limit = QUEUED_POLLS) {
  let queuedSeen = "";
  let queuedPolls = 0;
  return (data: FilesResponse) => {
    if (data.files.some((f) => f.leo !== null && INDEXING.has(f.leo.status))) return true;
    const queued = data.files
      .filter((f) => f.leo?.status === "queued")
      .map((f) => f.id)
      .join();
    if (queued !== queuedSeen) {
      queuedSeen = queued;
      queuedPolls = 0;
    }
    return queued !== "" && queuedPolls++ < limit;
  };
}

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

export const filesResource = createPollingResource(async () => withoutPending(await filesApi.list()), indexingPoller());

export const pendingDeletes = pending;

export const useFiles = () => usePollingResource(filesResource);
