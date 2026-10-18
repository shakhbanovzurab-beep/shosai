import { effectiveEntitlements } from "@/features/upgrade/mocks/demo-plans";

import { type FileFolder, type FileItem, type FileUpdate, type FolderUpdate, isLeoReadable } from "../domain/contract";
import type { StoredFile } from "./demo-files";
import { findFile, findFolder, leoBytes, present, store, syncIndex } from "./demo-store";
import { claimUpload, unclaimUpload } from "./demo-uploads";
import { isProblem, type Problem, problem } from "./problems";

/* Changes to the demo's files and folders. Each answers the new state, null for "not found", or a problem. */

const MB = 1024 * 1024;

/** The problem when a change would put more into Leo's index than the plan allows, or null. */
function overLeoLimit(): Problem | null {
  const limitMb = effectiveEntitlements()?.knowledge_base_mb;
  if (limitMb === null || limitMb === undefined) return null;
  return leoBytes(store) > limitMb * MB ? problem("leo_limit", 409, { limit_bytes: limitMb * MB }) : null;
}

/** Runs a change and undoes it when it would overfill Leo's index. */
function withinLimit(change: () => void): Problem | null {
  const files = store.files.map((f) => ({ ...f }));
  const folders = store.folders.map((f) => ({ ...f }));
  change();
  const refused = overLeoLimit();
  if (refused) {
    store.files = files;
    store.folders = folders;
  }
  return refused;
}

/** Ready uploads become files; a repeat answers the same files, as the backend does. */
export function addFiles(uploadIds: string[], folderId: string | null, leo: boolean): FileItem[] | Problem {
  if (folderId && !findFolder(folderId)) return problem("folder_not_found", 409);
  const added: StoredFile[] = [];
  for (const id of uploadIds) {
    if (findFile(id)) continue;
    const upload = claimUpload(id);
    if (isProblem(upload)) return upload;
    if (leo && !isLeoReadable(upload.filename, upload.size_bytes)) {
      unclaimUpload(id);
      return problem("leo_unreadable", 409);
    }
    const now = new Date().toISOString();
    added.push({
      id,
      name: upload.filename,
      content_type: upload.content_type,
      size_bytes: upload.size_bytes,
      folder_id: folderId,
      modified_at: now,
      starred: false,
      leo_on: leo,
      index_started_at: null,
    });
  }
  const refused = withinLimit(() => {
    store.files.unshift(...added);
    for (const file of added) syncIndex(store, file);
  });
  if (refused) for (const file of added) unclaimUpload(file.id);
  return refused ?? uploadIds.flatMap((id) => findFile(id) ?? []).map((f) => present(f));
}

export function updateFile(id: string, patch: FileUpdate): FileItem | Problem | null {
  const file = findFile(id);
  if (!file) return null;
  if (patch.folder_id && !findFolder(patch.folder_id)) return problem("folder_not_found", 409);
  if (patch.leo && !isLeoReadable(patch.name ?? file.name, file.size_bytes)) return problem("leo_unreadable", 409);
  const refused = withinLimit(() => {
    if (patch.name !== undefined) file.name = patch.name;
    if (patch.folder_id !== undefined) file.folder_id = patch.folder_id;
    if (patch.starred !== undefined) file.starred = patch.starred;
    if (patch.leo !== undefined) file.leo_on = patch.leo;
    if (patch.name !== undefined) file.modified_at = new Date().toISOString();
    syncIndex(store, file);
  });
  const current = findFile(id);
  return refused ?? (current ? present(current) : null);
}

/** "Report.pdf" → "Report (2).pdf", the first number no file in the folder holds, as the backend names copies. */
function copyName(name: string, folderId: string | null) {
  const taken = new Set(store.files.filter((f) => f.folder_id === folderId).map((f) => f.name));
  const dot = name.lastIndexOf(".");
  const [base, extension] = dot > 0 ? [name.slice(0, dot), name.slice(dot)] : [name, ""];
  for (let n = 2; ; n++) if (!taken.has(`${base} (${n})${extension}`)) return `${base} (${n})${extension}`;
}

/** A copy starts as just a file; Leo reads it only if its folder says so. */
export function copyFile(id: string): FileItem | null {
  const source = findFile(id);
  if (!source) return null;
  const copy: StoredFile = {
    ...source,
    id: crypto.randomUUID(),
    name: copyName(source.name, source.folder_id),
    starred: false,
    leo_on: false,
    index_started_at: null,
  };
  store.files.splice(store.files.indexOf(source) + 1, 0, copy);
  syncIndex(store, copy);
  return present(copy);
}

export function reindexFile(id: string): FileItem | Problem | null {
  const file = findFile(id);
  if (!file) return null;
  if (file.index_started_at === null) return problem("leo_not_used", 409);
  file.index_started_at = Date.now();
  return present(file);
}

export function createFolder(name: string): FileFolder {
  const folder = { id: crypto.randomUUID(), name, updated_at: new Date().toISOString(), leo: false };
  store.folders.push(folder);
  return folder;
}

export function updateFolder(id: string, patch: FolderUpdate): FileFolder | Problem | null {
  const folder = findFolder(id);
  if (!folder) return null;
  const refused = withinLimit(() => {
    const target = findFolder(id);
    if (!target) return;
    if (patch.name !== undefined) target.name = patch.name;
    if (patch.leo !== undefined) target.leo = patch.leo;
    target.updated_at = new Date().toISOString();
    for (const file of store.files) if (file.folder_id === id) syncIndex(store, file);
  });
  return refused ?? findFolder(id) ?? null;
}

/** Its files move to My files; Leo keeps only the ones chosen on their own. */
export function deleteFolder(id: string) {
  if (!findFolder(id)) return false;
  store.folders = store.folders.filter((f) => f.id !== id);
  for (const file of store.files) {
    if (file.folder_id !== id) continue;
    file.folder_id = null;
    syncIndex(store, file);
  }
  return true;
}
