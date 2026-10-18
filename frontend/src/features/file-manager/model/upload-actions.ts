"use client";

import { toast } from "sonner";

import { filesApi } from "../api/files-api";
import { filesResource } from "./files-resource";
import { describeError } from "./problem-words";
import { storageResource } from "./storage-resource";
import { startBatch } from "./upload-progress";
import { browserUploadPorts, runLimited, uploadFile } from "./uploads";
import type { FileActionWords } from "./words";

// Сколько файлов одной пачки идут в бакет одновременно (у каждого ещё до трёх частей сразу).
const FILE_CONCURRENCY = 2;

/**
 * Uploads the files straight to the bucket, then makes the ready ones files of My files (or of the folder) in
 * one request. A file that fails doesn't stop the others; the toasts say what went in and what didn't.
 */
export async function uploadFiles(
  files: File[],
  options: { folderId: string | null; leo: boolean },
  words: FileActionWords,
) {
  const { t } = words;
  const progress = startBatch(files.map((file) => file.size));
  const ready: string[] = [];
  const failed: { name: string; error: unknown }[] = [];
  try {
    await runLimited([...files.entries()], FILE_CONCURRENCY, async ([index, file]) => {
      try {
        ready.push(await uploadFile(file, browserUploadPorts, (bytes) => progress.sent(index, bytes)));
      } catch (error) {
        failed.push({ name: file.name, error });
      }
    });
  } finally {
    progress.finish();
  }
  const [first] = failed;
  if (first && failed.length === 1)
    toast.error(t("uploadFailedNamed", { name: first.name }), { description: describeError(first.error, words) });
  else if (first)
    toast.error(t("uploadFailedMany", { count: failed.length }), { description: describeError(first.error, words) });
  if (ready.length === 0) return false;
  try {
    const { files: added } = await filesApi.register(ready, options);
    filesResource.update((data) => ({ ...data, files: [...added, ...data.files] }));
    announce(added, options.folderId, words);
    return failed.length === 0;
  } catch (error) {
    toast.error(t("uploadFailed"), { description: describeError(error, words) });
    return false;
  } finally {
    void storageResource.refresh();
  }
}

function announce(added: { name: string; leo: unknown }[], folderId: string | null, { t }: FileActionWords) {
  const state = filesResource.getSnapshot();
  const folder = state.status === "ready" ? state.data.folders.find((f) => f.id === folderId) : undefined;
  const leo = added.some((f) => f.leo);
  let description: string | undefined;
  if (leo) description = added.length === 1 ? t("leoReadingFile") : t("leoReadingFiles");
  if (leo && folder?.leo) description = t("leoReadsFolder", { folder: folder.name });
  const [only] = added;
  const title =
    added.length === 1 && only ? t("uploadedFile", { name: only.name }) : t("uploadedFiles", { count: added.length });
  toast.success(title, { description });
}
