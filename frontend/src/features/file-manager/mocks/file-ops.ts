import { effectiveEntitlements } from "@/features/upgrade/mocks/demo-plans";

import type { FileFolder, FileItem, FileUpdate, FolderUpdate } from "../domain/contract";
import { copyName } from "../domain/files";
import type { StoredFile } from "./demo-files";
import { contentTypeOf } from "./demo-files";
import { findFile, findFolder, leoBytes, present, store, syncIndex } from "./demo-store";
import type { Problem } from "./problems";

/* Changes to the demo's files and folders. Each answers the new state, null for "not found", or a reason it can't. */

const MB = 1024 * 1024;

/** The reason a change would put more into Leo's index than the plan allows, or null. */
function overLeoLimit(): Problem | null {
  const limitMb = effectiveEntitlements()?.knowledge_base_mb;
  if (limitMb === null || limitMb === undefined) return null;
  return leoBytes(store) > limitMb * MB ? { code: "overLeoLimit", bytes: limitMb * MB } : null;
}

/** Runs a change and undoes it when it would overfill Leo's index. */
function withinLimit(snapshot: () => () => void, change: () => void): Problem | null {
  const restore = snapshot();
  change();
  const refused = overLeoLimit();
  if (refused) restore();
  return refused;
}

const snapshotFiles = () => {
  const saved = store.files.map((f) => ({ ...f }));
  const folders = store.folders.map((f) => ({ ...f }));
  return () => {
    store.files = saved;
    store.folders = folders;
  };
};

export function addFiles(uploads: File[], folderId: string | null, leo: boolean): FileItem[] | Problem {
  if (folderId && !findFolder(folderId)) return { code: "folderGone" };
  const now = Date.now();
  const added: StoredFile[] = uploads.map((upload) => ({
    id: crypto.randomUUID(),
    name: upload.name,
    content_type: upload.type || contentTypeOf(upload.name),
    size_bytes: upload.size,
    folder_id: folderId,
    modified_at: new Date(now).toISOString(),
    starred: false,
    leo_on: leo,
    index_started_at: null,
  }));
  const refused = withinLimit(snapshotFiles, () => {
    store.files.unshift(...added);
    for (const file of added) syncIndex(store, file, now);
  });
  return refused ?? added.map((f) => present(f, now));
}

export function updateFile(id: string, patch: FileUpdate): FileItem | Problem | null {
  const file = findFile(id);
  if (!file) return null;
  if (patch.folder_id && !findFolder(patch.folder_id)) return { code: "folderGone" };
  const refused = withinLimit(snapshotFiles, () => {
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

/** `copyOf` words the copy's name in the request's language ("Report" → "Report copy"). */
export function copyFile(id: string, copyOf: (base: string) => string): FileItem | null {
  const source = findFile(id);
  if (!source) return null;
  const copy: StoredFile = {
    ...source,
    id: crypto.randomUUID(),
    name: copyName(source.name, copyOf),
    modified_at: new Date().toISOString(),
    starred: false,
    // A copy starts as just a file; Leo reads it only if its folder says so.
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
  if (file.index_started_at === null) return { code: "notUsedByLeo" };
  file.index_started_at = Date.now();
  return present(file);
}

export function createFolder(name: string) {
  const folder = { id: crypto.randomUUID(), name, updated_at: new Date().toISOString(), leo: false };
  store.folders.push(folder);
  return folder;
}

export function updateFolder(id: string, patch: FolderUpdate): FileFolder | Problem | null {
  const folder = findFolder(id);
  if (!folder) return null;
  const refused = withinLimit(snapshotFiles, () => {
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
