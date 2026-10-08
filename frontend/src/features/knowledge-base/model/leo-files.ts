import { toast } from "sonner";

import {
  type FileFolder,
  type FileItem,
  IN_PROGRESS,
  type IndexStatus,
  isLeoReadable,
  type LeoUse,
  MAX_FILES_PER_UPLOAD,
} from "@/features/file-manager/domain/contract";
import { setFileLeo } from "@/features/file-manager/model/file-actions";
import { setFolderLeo } from "@/features/file-manager/model/folder-actions";
import type { FileActionWords } from "@/features/file-manager/model/words";

import type { KnowledgeWords } from "./words";

/** The steps a file runs through before Leo can answer from it. */
export const PIPELINE: IndexStatus[] = ["queued", "parsing", "chunking", "embedding"];

/** Where a file being read is: its step (0-based) and its overall progress through the pipeline, in percent. */
export function pipelineProgress(leo: LeoUse) {
  const step = PIPELINE.indexOf(leo.status);
  const overall = Math.round(((step + leo.progress / 100) / PIPELINE.length) * 100);
  return { step, overall };
}

/** "PDF" for "report.pdf". */
export const fileExtension = (name: string) => name.slice(name.lastIndexOf(".") + 1).toUpperCase();

/** The files Leo uses, newest first. */
export const leoFiles = (files: FileItem[]) => files.filter((f): f is FileItem & { leo: LeoUse } => f.leo !== null);

/** Chunks in the index, files still being read, ones that failed, and how many bytes Leo uses. */
export function indexTotals(files: (FileItem & { leo: LeoUse })[]) {
  let chunks = 0;
  let processing = 0;
  let failed = 0;
  let bytes = 0;
  for (const file of files) {
    chunks += file.leo.status === "indexed" ? (file.leo.chunk_count ?? 0) : 0;
    if (IN_PROGRESS.has(file.leo.status)) processing++;
    if (file.leo.status === "failed") failed++;
    bytes += file.size_bytes;
  }
  return { chunks, processing, failed, bytes };
}

/** Why a picked file is left out: a type or size Leo can't read, or past the most one upload takes. */
export type Rejection = { name: string; reason: "unreadable" | "tooMany" };

/** Splits a selection into what Leo can read and a reason for everything else. */
export function triage<T extends { name: string; size: number }>(files: T[]) {
  const accepted: T[] = [];
  const rejected: Rejection[] = [];
  for (const file of files) {
    if (!isLeoReadable(file.name, file.size)) rejected.push({ name: file.name, reason: "unreadable" });
    else if (accepted.length >= MAX_FILES_PER_UPLOAD) rejected.push({ name: file.name, reason: "tooMany" });
    else accepted.push(file);
  }
  return { accepted, rejected };
}

/** Has Leo use the picked folders and files, with one confirmation for all of them. */
export async function chooseForLeo(
  folders: FileFolder[],
  files: FileItem[],
  t: KnowledgeWords,
  words: FileActionWords,
) {
  const results = await Promise.all([
    ...folders.map((folder) => setFolderLeo(folder, true, words, true)),
    ...files.map((file) => setFileLeo(file, true, words, true)),
  ]);
  const done = results.filter(Boolean).length;
  if (done)
    toast.success(done === 1 ? t("choose.readingOne") : t("choose.readingMany", { count: done }), {
      description: t("choose.readingDescription"),
    });
}
