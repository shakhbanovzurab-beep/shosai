import { type FileFolder, type FileItem, type IndexStatus, isLeoReadable, type LeoUse } from "../domain/contract";
import { kindOf } from "../domain/files";
import { type StoredFile, seedFiles, seedFolders } from "./demo-files";

/*
 * In-memory stand-in for the files service in `npm run dev` and tests. Nothing is stored or parsed: a file Leo
 * uses walks through the index pipeline on a timer. Resets on reload.
 */

export type Store = { folders: FileFolder[]; files: StoredFile[] };

/** Milliseconds each step takes in the demo, cumulative. */
const STEPS: [IndexStatus, number][] = [
  ["queued", 800],
  ["parsing", 2200],
  ["chunking", 3200],
  ["embedding", 6500],
];

/** Tokens a chunk holds in the demo index, after overlap; at roughly 4 bytes a token. */
const CHUNK_TOKENS = 680;
const chunksOf = (bytes: number) => Math.max(1, Math.ceil(bytes / 4 / CHUNK_TOKENS));

const DAY_MS = 86_400_000;

function folderOf(s: Store, file: StoredFile) {
  return s.folders.find((f) => f.id === file.folder_id);
}

export function usesLeo(s: Store, file: StoredFile) {
  return isLeoReadable(file.name, file.size_bytes) && (file.leo_on || folderOf(s, file)?.leo === true);
}

function seed(): Store {
  const store = { folders: seedFolders(), files: seedFiles() };
  for (const file of store.files) if (usesLeo(store, file)) file.index_started_at = Date.now() - DAY_MS;
  return store;
}

// On globalThis so every route handler bundle shares one store within the server process.
const shared = globalThis as typeof globalThis & { fileManagerDemo?: Store };
shared.fileManagerDemo ??= seed();
export const store = shared.fileManagerDemo;

/** Starts reading a file Leo now uses, and forgets the index of one it no longer does. */
export function syncIndex(s: Store, file: StoredFile, now = Date.now()) {
  if (!usesLeo(s, file)) file.index_started_at = null;
  else file.index_started_at ??= now;
}

function leoUse(s: Store, file: StoredFile, now: number): LeoUse | null {
  if (file.index_started_at === null || !usesLeo(s, file)) return null;
  const via = file.leo_on ? "file" : "folder";
  const elapsed = now - file.index_started_at;
  let stepStart = 0;
  for (const [status, end] of STEPS) {
    if (elapsed < end) {
      const progress = Math.round(((elapsed - stepStart) / (end - stepStart)) * 100);
      const chunk_count = status === "embedding" ? chunksOf(file.size_bytes) : null;
      return { via, status, progress, chunk_count, error: null };
    }
    stepStart = end;
  }
  return { via, status: "indexed", progress: 100, chunk_count: chunksOf(file.size_bytes), error: null };
}

export function present(file: StoredFile, now = Date.now()): FileItem {
  const { leo_on: _own, index_started_at: _started, ...rest } = file;
  return {
    ...rest,
    kind: kindOf(file.name),
    leo_readable: isLeoReadable(file.name, file.size_bytes),
    leo: leoUse(store, file, now),
  };
}

/** Bytes of every file Leo uses: what the plan's knowledge limit counts. */
export const leoBytes = (s: Store) => s.files.reduce((sum, f) => sum + (usesLeo(s, f) ? f.size_bytes : 0), 0);

/** Bytes every file holds: what the plan's storage counts. */
export const usedBytes = () => store.files.reduce((sum, f) => sum + f.size_bytes, 0);

export const findFile = (id: string) => store.files.find((f) => f.id === id);
export const findFolder = (id: string) => store.folders.find((f) => f.id === id);
