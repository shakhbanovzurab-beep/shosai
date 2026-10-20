"use client";

import { toast } from "sonner";

import { browserUploadPorts, runLimited, uploadFile } from "@/lib/uploads/upload-file";

import { filesApi } from "../api/files-api";
import { fileProblemOf } from "../domain/problems";
import type { Refusal } from "../domain/upload-queue";
import { filesResource } from "./files-resource";
import { describeError } from "./problem-words";
import { storageResource } from "./storage-resource";
import { isTrayShown, type UploadTarget, uploadQueue } from "./upload-queue";
import type { FileActionWords } from "./words";

// Сколько файлов одной пачки идут в бакет одновременно (у каждого ещё до трёх частей сразу).
const FILE_CONCURRENCY = 2;
const FILE_PORTS = browserUploadPorts("file_manager");
// Так регистрация говорит, что готовой загрузки больше нет: повтор отправит байты заново.
const UPLOAD_GONE: ReadonlySet<string> = new Set(["upload_not_claimable", "upload_not_found", "upload_closed"]);

type Ready = { id: string; name: string; uploadId: string };
type Failure = { name: string; error: unknown };
type Sent = { ready: Ready } | { failure: Failure } | null;

/** Files refused before they started: rows of the panel with their reason. */
export function refuseFiles(refused: readonly { file: File; refusal: Refusal }[], target: UploadTarget) {
  for (const { file, refusal } of refused) uploadQueue.refuse(file, target, refusal);
}

/**
 * Uploads the files straight to the bucket, then makes the ready ones files of My files (or of the folder) in
 * one request. A file that fails doesn't stop the others. Каждый файл виден строкой панели; тосты говорят,
 * только когда панели нет на экране.
 */
export async function uploadFiles(files: File[], target: UploadTarget, words: FileActionWords) {
  const ids = files.map((file) => uploadQueue.add(file, target));
  const ready: Ready[] = [];
  const failed: Failure[] = [];
  await runLimited(ids, FILE_CONCURRENCY, async (id) => {
    const sent = await send(id);
    if (sent && "ready" in sent) ready.push(sent.ready);
    if (sent && "failure" in sent) failed.push(sent.failure);
  });
  failed.push(...(await register(ready, target, words)));
  tellFailures(failed, words);
}

/** Sends a failed row again; a row whose bytes already reached the bucket is only registered again. */
export async function retryUpload(id: string, words: FileActionWords) {
  const retry = uploadQueue.retryOf(id);
  if (!retry) return;
  let ready: Ready | null = null;
  if (retry.uploadId === null) {
    const sent = await send(id);
    if (sent && "failure" in sent) tellFailures([sent.failure], words);
    if (sent && "ready" in sent) ready = sent.ready;
  } else {
    uploadQueue.saving(id, retry.uploadId);
    ready = { id, name: retry.name, uploadId: retry.uploadId };
  }
  if (ready) tellFailures(await register([ready], retry.target, words), words);
}

async function send(id: string): Promise<Sent> {
  const started = uploadQueue.start(id);
  if (!started) return null;
  const { file, signal } = started;
  try {
    const uploadId = await uploadFile(file, FILE_PORTS, (bytes) => uploadQueue.sent(id, bytes), signal);
    uploadQueue.saving(id, uploadId);
    return { ready: { id, name: file.name, uploadId } };
  } catch (error) {
    // Отменённая строка уже убрана из панели: сообщать не о чем.
    if (signal.aborted) return null;
    uploadQueue.fail(id, error, true);
    return { failure: { name: file.name, error } };
  }
}

async function register(ready: Ready[], target: UploadTarget, words: FileActionWords): Promise<Failure[]> {
  if (ready.length === 0) return [];
  try {
    const { files: added } = await filesApi.register(
      ready.map((item) => item.uploadId),
      target,
    );
    filesResource.update((data) => ({ ...data, files: [...added, ...data.files] }));
    for (const { id } of ready) uploadQueue.done(id);
    if (!isTrayShown()) announce(added, target.folderId, words);
    return [];
  } catch (error) {
    const gone = UPLOAD_GONE.has(fileProblemOf(error)?.code ?? "");
    for (const { id } of ready) uploadQueue.fail(id, error, gone);
    return ready.map(({ name }) => ({ name, error }));
  } finally {
    void storageResource.refresh();
  }
}

function tellFailures(failed: Failure[], words: FileActionWords) {
  const [first] = failed;
  if (!first || isTrayShown()) return;
  const description = describeError(first.error, words);
  if (failed.length === 1) toast.error(words.t("uploadFailedNamed", { name: first.name }), { description });
  else toast.error(words.t("uploadFailedMany", { count: failed.length }), { description });
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
