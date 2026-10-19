import { toast } from "sonner";

import {
  type FileFolder,
  type FileItem,
  IN_PROGRESS,
  type IndexStatus,
  type LeoUse,
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
